"""Part 3 — GenAI insight narrator (Situation–Complication–Resolution).

Reads narrator/findings.json (written by analysis/clean_and_eda.py) and produces an SCR narrative.

    python narrator/generate_narrative.py                 # uses Gemini if a key is set, else offline
    python narrator/generate_narrative.py --offline       # force the keyless deterministic path
    python narrator/generate_narrative.py --save-sample   # also write narrator/sample_output.txt
    python narrator/generate_narrative.py --check-file narrator/sample_output.txt

API key (free tier, Google AI Studio):  export GEMINI_API_KEY="..."   (GOOGLE_API_KEY also accepted)
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINDINGS_PATH = HERE / "findings.json"
SAMPLE_PATH = HERE / "sample_output.txt"
MODEL = "gemini-2.5-flash"  # available on the free tier

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a concise business narrative (about 250 words) in the SCR structure with exactly three "
    "labeled sections, in this order: 'Situation', 'Complication', 'Resolution'. "
    "Every number in your output MUST come from the findings supplied by the user and appear with "
    "exactly the same value — do not invent, estimate, round differently, or derive any new statistic. "
    "Write money as INR with thousands separators and two decimals. Plain text, no tables."
)


# ----------------------------------------------------------------------------- helpers
def month_name(ym: str) -> str:
    return datetime.strptime(ym, "%Y-%m").strftime("%B")


def inr(x: float) -> str:
    return f"{x:,.2f}"


def build_user_prompt(f: dict) -> str:
    """Interpolated entirely from `f` — a different findings.json yields a different prompt."""
    rates = ", ".join(f"{k} {v}%" for k, v in f["return_rate_by_payment"].items())
    seg, peak, inf = f["highest_risk_segment"], f["true_peak_month"], f["outlier_inflated_month"]
    return (
        "Verified findings (use these numbers verbatim):\n"
        f"- Cleaned total revenue: INR {inr(f['cleaned_total_revenue_inr'])}\n"
        f"- Raw total revenue before de-duplication: INR {inr(f['raw_total_revenue_inr'])}\n"
        f"- Revenue removed by deleting double-submitted duplicate orders: INR {inr(f['duplicate_reconciliation_delta_inr'])}\n"
        f"- Return rate by payment method: {rates}\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities, return rate {seg['return_rate_pct']}%\n"
        f"- True peak month: {month_name(peak['month'])} ({peak['month']}) at INR {inr(peak['revenue_inr'])}\n"
        f"- {month_name(inf['month'])} ({inf['month']}) looked like the peak at INR {inr(inf['apparent_revenue_inr'])} "
        f"but is INR {inr(inf['corrected_revenue_inr'])} once two bulk orders are excluded\n\n"
        "Write the Situation, Complication and Resolution sections now."
    )


# ----------------------------------------------------------------------------- online path
def call_gemini(findings: dict, api_key: str) -> dict:
    """One Gemini call. Always returns a dict: success {status, narrative, tokens} or error {status, narrative=None, message}."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=build_user_prompt(findings),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,   # role + structure + no-invented-numbers rule
                temperature=0.0,                          # factual business report, not creative writing:
                                                          # deterministic decoding keeps figures faithful
                max_output_tokens=1024,                   # explicit cap; ample for ~250 words / 3 sections
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # keep the budget for the answer
                http_options=types.HttpOptions(timeout=30_000),            # 30 s (milliseconds), >= 10 s minimum
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned an empty response")
        tokens = getattr(response.usage_metadata, "total_token_count", None)
        return {"status": "success", "narrative": text, "tokens": tokens}
    except Exception as err:  # the caller never receives a raw exception
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative(findings: dict) -> dict:
    """Gemini when a key is set; deterministic offline template when there is no key or the call errors."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        result = call_gemini(findings, api_key)
        if result["status"] == "success":
            result["source"] = f"gemini ({MODEL})"
            return result
        reason = f"Gemini call failed: {result['message'][:120]}"
    else:
        reason = "no API key configured"
    fallback = generate_scr_narrative_offline(findings)
    fallback["source"] = f"offline ({reason})"
    return fallback


# ----------------------------------------------------------------------------- offline path
def generate_scr_narrative_offline(findings: dict) -> dict:
    """Deterministic template — no network, no key, same return shape."""
    f = findings
    r, seg = f["return_rate_by_payment"], f["highest_risk_segment"]
    peak, inf = f["true_peak_month"], f["outlier_inflated_month"]
    pm = seg["payment_method"]
    narrative = f"""SITUATION
After cleaning the order data (standardised payment labels, removed double-submitted duplicates, imputed missing values), Mamaearth's verified revenue is INR {inr(f['cleaned_total_revenue_inr'])}. The raw feed showed INR {inr(f['raw_total_revenue_inr'])}; the INR {inr(f['duplicate_reconciliation_delta_inr'])} difference is entirely duplicate orders and nothing else. The true peak month is {month_name(peak['month'])}, at INR {inr(peak['revenue_inr'])}. {month_name(inf['month'])} only appeared to lead (INR {inr(inf['apparent_revenue_inr'])}) because two bulk orders landed in it; without them it was INR {inr(inf['corrected_revenue_inr'])}.

COMPLICATION
Returns are concentrated, not evenly spread. Cash-on-delivery orders are returned at {r['COD']}%, against {r['CARD']}% for card and {r['UPI']}% for UPI. The blended figure hides the worst pocket: {pm} orders in Tier-{seg['city_tier']} cities are returned at {seg['return_rate_pct']}%. Discounts do not explain this, so deeper promotions will not fix it.

RESOLUTION
Regional ops and finance should target the {pm} + Tier-{seg['city_tier']} segment first: pilot order confirmation calls or OTP-based delivery, nudge buyers toward prepaid payment, and track the return rate per segment each month. Report revenue on the de-duplicated, outlier-aware basis so {month_name(peak['month'])} is read as the genuine peak.
"""
    return {"status": "success", "narrative": narrative, "tokens": None}


# ----------------------------------------------------------------------------- accuracy checker
def check_narrative(narrative: str, findings: dict) -> bool:
    """Assert the five required figures appear (commas normalised); print a pass/fail line each."""
    text = narrative.replace(",", "")
    peak = findings["true_peak_month"]
    checks = [
        ("cleaned total revenue", f"{findings['cleaned_total_revenue_inr']:.2f}".rstrip("0").rstrip(".")),
        ("COD return rate", str(findings["return_rate_by_payment"]["COD"])),
        ("COD + Tier-2 segment rate", str(findings["highest_risk_segment"]["return_rate_pct"])),
        ("duplicate delta", f"{findings['duplicate_reconciliation_delta_inr']:.2f}".rstrip("0").rstrip(".")),
        ("peak month name", month_name(peak["month"])),
        ("peak month revenue", f"{peak['revenue_inr']:.2f}".rstrip("0").rstrip(".")),
    ]
    ok = True
    for label, needle in checks:
        hit = needle in text
        ok &= hit
        print(f"  [{'PASS' if hit else 'FAIL'}] {label}: {needle}")
    print("ALL FIGURES PRESENT" if ok else "MISSING FIGURES")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="force the keyless deterministic path")
    ap.add_argument("--save-sample", action="store_true", help="write narrator/sample_output.txt")
    ap.add_argument("--check-file", help="run the numeric checker on a saved narrative file and exit")
    args = ap.parse_args()

    findings = json.loads(FINDINGS_PATH.read_text())
    if args.check_file:
        print(f"Checking {args.check_file}")
        return 0 if check_narrative(Path(args.check_file).read_text(), findings) else 1

    result = generate_scr_narrative_offline(findings) if args.offline else generate_scr_narrative(findings)
    if args.offline:
        result["source"] = "offline (forced)"
    print(f"[source: {result.get('source')}]  [tokens: {result.get('tokens')}]\n")
    print(result["narrative"], "\n")
    ok = check_narrative(result["narrative"], findings)
    if args.save_sample:
        SAMPLE_PATH.write_text(f"# source: {result.get('source')}\n\n{result['narrative']}")
        print(f"Saved {SAMPLE_PATH.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
