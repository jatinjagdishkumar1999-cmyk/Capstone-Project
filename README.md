# Mamaearth Returns & Growth Intelligence Pipeline

An end-to-end pipeline that proves where returns are eating margin: **SQL** store → **pandas** analysis → **GenAI** narrative.
Each layer only reports numbers it computed itself or received from the layer before it.

```
data/*.csv ──► sql/ (SQLite reports)            Part 1  — relational layer
     │
     └───────► analysis/clean_and_eda.py ──► narrator/findings.json ──► narrator/generate_narrative.py
               analysis/visualize.py ──► visualizations/*.png          Part 2 → Part 3
```

## Repo structure

```
README.md
requirements.txt
sql/            schema.sql · seed_data.sql · reports.sql        (Part 1)
data/           customers.csv · products.csv · orders.csv       (raw source data — never edited)
analysis/       clean_and_eda.py · visualize.py                  (Part 2)
visualizations/ return_rate_by_payment.png · monthly_revenue_trend.png
narrator/       findings.json · generate_narrative.py · sample_output.txt   (Part 3)
```

## Setup

```bash
pip install pandas numpy matplotlib          # required
pip install google-genai                     # optional: only for the online Gemini path
```

## Run order

### 1. SQL layer (Part 1)

```bash
sqlite3 mamaearth.db < sql/schema.sql        # creates 3 tables (drops/recreates, re-runnable)
sqlite3 mamaearth.db < sql/seed_data.sql     # loads the CSVs; prints counts 45 / 16 / 180
sqlite3 -header -column mamaearth.db < sql/reports.sql
```

No `sqlite3` CLI? Use Python: `python -c "import sqlite3;c=sqlite3.connect('mamaearth.db');[c.executescript(open(f'sql/{f}.sql').read()) for f in ('schema','seed_data')]"`.

`seed_data.sql` is generated from `data/*.csv` with blank cells written as `NULL` (so `COUNT(rating)` = 165, not 180).
`reports.sql` runs on the **raw, uncleaned** data; the real output of each query is pasted as a comment above it.
Key results: 180 orders · ₹99,860.20 raw revenue · 15 unrated orders · C045 Vihaan has no orders · Jaipur/Lucknow/Bangalore exceed 20% returns.

### 2. Analysis layer (Part 2)

```bash
python analysis/clean_and_eda.py     # cleaning + EDA, prints every intermediate result
python analysis/visualize.py         # writes visualizations/*.png
```

`clean_and_eda.py` reads the CSVs directly (independent of the database), so Parts 1 and 2 can run in either order.
**Its final step (the Task 5/10 results) writes `narrator/findings.json`** — nothing in that file is hand-typed.

Headline results: 7 → 3 payment labels · 5 duplicates dropped (O0176–O0180) → 175 rows · cleaned revenue ₹97,358.30,
₹2,501.90 below the raw total — exactly the 5 duplicates · COD returns 44.4% (CARD 14.7%, UPI 18.9%) ·
riskiest segment COD + Tier-2 at 54.5% · all correlations negligible · March (₹20,318.90) is the true peak;
January's 29,582.10 is inflated by bulk orders O0011 and O0098.

### 3. Narrator layer (Part 3)

```bash
# No key at all -> deterministic offline narrative (zero configuration):
python narrator/generate_narrative.py

# With Gemini (free key from Google AI Studio, https://aistudio.google.com/apikey):
export GEMINI_API_KEY="your-key"          # Windows PowerShell: $env:GEMINI_API_KEY="your-key"
python narrator/generate_narrative.py --save-sample     # writes narrator/sample_output.txt

# Re-check a saved narrative against findings.json:
python narrator/generate_narrative.py --check-file narrator/sample_output.txt
```

- Gemini path: `google-genai` client, system instruction fixing role + Situation/Complication/Resolution structure +
  "no invented numbers", `temperature=0.0`, `max_output_tokens=1024`, 30 s timeout, all in `try/except`
  returning `{"status": ..., "narrative": ..., "tokens": ...}` or `{"status": "error", "narrative": None, "message": ...}`.
- If no key is set, or the API call errors, it automatically falls back to `generate_scr_narrative_offline()` — a template built from `findings.json`.
- Every run prints a pass/fail checker for the five required figures: 97,358.30 · 44.4 · 54.5 · 2,501.90 · March + 20,318.90.

> **Note on `sample_output.txt`:** the one committed in this repo was produced by the **offline** path (its first line says so).
> To satisfy the Gemini-sample requirement, set your free key and re-run with `--save-sample` before submitting, then commit the file.

## How data flows between layers

| From | To | What moves |
|---|---|---|
| `data/*.csv` | `sql/seed_data.sql` | Row-for-row INSERTs; blanks become `NULL` |
| `data/*.csv` | `analysis/clean_and_eda.py` | Same raw files, read with pandas |
| SQL Report (a) raw total ₹99,860.20 | Part 2 reconciliation | Re-computed in pandas on raw data; delta to cleaned total is proven to equal the 5 duplicates |
| `clean_and_eda.py` | `narrator/findings.json` | The seven verified figures, written by code |
| `findings.json` | `generate_narrative.py` | Prompt and offline template are interpolated from it — change the JSON, the narrative changes |
