# Who delivers under pressure? — SupeRR Selector Season 2

A reproducible pipeline that measures how IPL and T20I batters and bowlers (2022–2026) perform in
high-pressure moments compared with their usual level, and ranks the most reliable performers for
Rajasthan Royals' IPL 2027 auction.

## Reproduce
1. Put the data pack CSVs in `data/raw/` (the data is not included in this repo).
2. Set up Python:
   ```
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Run the scripts in `src/` in number order, starting with `python src/01_clean.py`.

The method is described in `docs/METHODOLOGY_SPEC.md`, and every decision is logged in `DECISIONS.md`.
