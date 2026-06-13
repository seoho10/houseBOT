# houseBOT

Daily Naver real estate listing tracker. Reads tracked complexes from a Google Sheet, scrapes listings from `new.land.naver.com`, detects changes vs. prior snapshots, and posts summaries to Telegram.

See `docs/superpowers/specs/2026-06-13-housebot-design.md` for the design and `docs/superpowers/plans/2026-06-13-housebot-plan.md` for the implementation plan.

## Local setup
1. Install Python 3.11+
2. `python -m venv .venv && .venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux)
3. `pip install -e ".[dev]"`
4. Copy `.env.example` to `.env` and fill in values
5. `pytest`

## Run modes
- `python -m src.run_daily` — full daily summary (08:30 KST in production)
- `python -m src.run_check` — light change check (every 2h in production)
- Set `DRY_RUN=true` to skip Telegram/Sheets writes (console output only)
