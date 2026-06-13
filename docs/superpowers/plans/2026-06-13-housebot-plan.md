# houseBOT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python bot that scrapes Naver real estate listings for tracked apartment complexes, stores history in Google Sheets, and sends summary/change notifications to Telegram on a cron schedule via GitHub Actions.

**Architecture:** Seven small Python modules (config, naver_scraper, sheets_store, analyzer, telegram_notifier, run_daily, run_check) with single-direction dependencies. The analyzer is pure (no I/O), the scraper isolates Naver-specific quirks, the store hides Sheets shape, and two thin entrypoints orchestrate the daily summary and 2-hour light-check flows. GitHub Actions cron triggers both flows.

**Tech Stack:** Python 3.11+, httpx (HTTP), gspread (Google Sheets), pytest + pytest-mock (test), GitHub Actions (cron + secrets), Telegram Bot API.

**Spec reference:** `docs/superpowers/specs/2026-06-13-housebot-design.md`

---

## Conventions

- All commits use Conventional Commits (`feat:`, `test:`, `docs:`, `chore:`, `fix:`).
- Every code task is **test-first**: write failing test, run it (must fail for the right reason), implement, run again (must pass), then commit.
- Run all commands from the project root: `C:/Users/user/Desktop/project/houseBOT/`.
- Use PowerShell or Bash — both work, examples use Bash-style.
- File paths are absolute when shown for `Create`/`Modify`/`Test`; commands use relative paths.

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1.1: Create `pyproject.toml`**

```toml
[project]
name = "housebot"
version = "0.1.0"
description = "Daily Naver real estate listing tracker with Telegram alerts"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "gspread>=6.0.0",
    "google-auth>=2.28.0",
    "tenacity>=8.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 1.2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/

# Secrets
.env
.env.local
google-sa.json
*.pem

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 1.3: Create `.env.example`**

```
TELEGRAM_BOT_TOKEN=000000:replace-with-real-token
TELEGRAM_CHAT_ID=000000000
GOOGLE_SHEETS_ID=replace-with-sheet-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
DRY_RUN=false
```

- [ ] **Step 1.4: Create `README.md`**

```markdown
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
```

- [ ] **Step 1.5: Create empty package init files**

`src/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 1.6: Create `tests/conftest.py`**

```python
import os
import pytest

@pytest.fixture
def fixture_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
```

- [ ] **Step 1.7: Create fixtures placeholder**

`tests/fixtures/.gitkeep`:
```
```

- [ ] **Step 1.8: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: pip output ending with `Successfully installed ...`

- [ ] **Step 1.9: Verify pytest discovers no tests yet**

Run: `pytest`
Expected: `no tests ran in 0.0Xs` (exit code 5)

- [ ] **Step 1.10: Commit**

```bash
git add pyproject.toml .gitignore .env.example README.md src/ tests/
git commit -m "chore: scaffold project structure with pyproject and pytest"
```

---

## Task 2: Google Cloud service account setup (manual)

This is a one-time external setup. It produces the JSON credential the bot uses to write to Google Sheets. No code in this task.

- [ ] **Step 2.1: Create a Google Cloud project**

1. Go to https://console.cloud.google.com/
2. Top bar → project dropdown → "New Project"
3. Name: `houseBOT`
4. Create

- [ ] **Step 2.2: Enable the Google Sheets API**

1. In the project, sidebar → "APIs & Services" → "Library"
2. Search "Google Sheets API" → click it → "Enable"
3. Also search "Google Drive API" → "Enable" (gspread needs it to open files by ID)

- [ ] **Step 2.3: Create a service account**

1. Sidebar → "IAM & Admin" → "Service Accounts" → "Create service account"
2. Name: `housebot-sa`
3. Skip optional role assignment → "Done"

- [ ] **Step 2.4: Generate a key**

1. In the service accounts list, click `housebot-sa`
2. Tab "Keys" → "Add Key" → "Create new key" → JSON → Create
3. A JSON file downloads — save as `google-sa.json` somewhere safe (NOT in the repo)

- [ ] **Step 2.5: Share the Sheets document with the service account**

1. Open `google-sa.json`, copy the `client_email` value (looks like `housebot-sa@houseBOT.iam.gserviceaccount.com`)
2. Open the `HouseBOT` Google Sheet in browser
3. "Share" button (top right) → paste the client_email → role "Editor" → uncheck "Notify people" → Send
4. The sheet is now writable by the service account

- [ ] **Step 2.6: Stash credentials in `.env` for local use**

Edit `.env` (copy from `.env.example` first if needed):
```
TELEGRAM_BOT_TOKEN=<your real bot token>
TELEGRAM_CHAT_ID=<your real chat id>
GOOGLE_SHEETS_ID=<id from the sheet URL between /d/ and /edit>
GOOGLE_SERVICE_ACCOUNT_JSON=<entire contents of google-sa.json, on one line — escape newlines or use python -c to compact>
```

To compact the JSON to one line:
```bash
python -c "import json; print(json.dumps(json.load(open('path/to/google-sa.json'))))"
```
Copy the printed output as the value.

- [ ] **Step 2.7: Verify `.env` is gitignored**

Run: `git status`
Expected: `.env` does NOT appear in untracked files (because `.gitignore` excludes it).

No commit for this task — credentials stay local.

---

## Task 3: `config.py` — Settings and apartment dataclasses

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 3.1: Write failing test for environment loading**

`tests/test_config.py`:
```python
import os
import json
import pytest
from src.config import Settings, load_settings


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheetid")
    sa_json = json.dumps({"type": "service_account", "client_email": "a@b.com"})
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", sa_json)
    monkeypatch.setenv("DRY_RUN", "false")

    s = load_settings()

    assert s.telegram_bot_token == "tok123"
    assert s.telegram_chat_id == "456"
    assert s.sheets_id == "sheetid"
    assert s.google_sa_info["client_email"] == "a@b.com"
    assert s.dry_run is False


def test_load_settings_dry_run_true(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheetid")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setenv("DRY_RUN", "true")

    s = load_settings()
    assert s.dry_run is True


def test_load_settings_missing_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        load_settings()
```

- [ ] **Step 3.2: Run test, verify failure**

Run: `pytest tests/test_config.py -v`
Expected: ModuleNotFoundError or ImportError for `src.config`.

- [ ] **Step 3.3: Implement `src/config.py`**

```python
"""Environment-based settings and apartment config types."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    sheets_id: str
    google_sa_info: dict
    dry_run: bool


@dataclass(frozen=True)
class ApartmentConfig:
    name: str
    complex_id: str
    interested_sizes: tuple[str, ...]
    active: bool


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
        sheets_id=_require_env("GOOGLE_SHEETS_ID"),
        google_sa_info=json.loads(_require_env("GOOGLE_SERVICE_ACCOUNT_JSON")),
        dry_run=os.environ.get("DRY_RUN", "false").lower() == "true",
    )
```

- [ ] **Step 3.4: Run tests, verify pass**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 3.5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add Settings and ApartmentConfig with env loader"
```

---

## Task 4: `analyzer.py` data types and `detect_changes`

**Files:**
- Create: `src/analyzer.py`
- Create: `src/models.py`
- Test: `tests/test_analyzer.py`

We introduce a `src/models.py` for shared dataclasses so analyzer, scraper, and store can all import them without a cycle.

- [ ] **Step 4.1: Create shared models**

`src/models.py`:
```python
"""Shared data models used across scraper, analyzer, store, notifier."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EventKind = Literal["NEW_LISTING", "PRICE_CHANGE", "LISTING_REMOVED"]


@dataclass(frozen=True)
class Listing:
    article_id: str
    complex_id: str
    size_label: str          # e.g. "84" for grouping (rounded 전용면적 in ㎡)
    size_sqm: float          # raw 전용면적
    price_manwon: int        # price in 만원 units
    building: str            # e.g. "101동" — may be empty
    floor: str               # e.g. "12층" or "중층" — may be empty
    direction: str           # e.g. "남향" — may be empty
    registered_ymd: str      # YYYY-MM-DD or empty
    article_url: str


@dataclass(frozen=True)
class Event:
    kind: EventKind
    complex_id: str
    article_id: str
    detail: str
    article_url: str


@dataclass(frozen=True)
class SizeSummary:
    size_label: str
    count: int
    min_price: int
    avg_price: int
    max_price: int
```

- [ ] **Step 4.2: Write failing test for `detect_changes`**

`tests/test_analyzer.py`:
```python
from src.models import Listing
from src.analyzer import detect_changes


def L(article_id="a1", complex_id="8692", price=125000, size="84"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label=size,
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_detect_new_listing():
    prev = []
    curr = [L(article_id="a1")]
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "NEW_LISTING"
    assert events[0].article_id == "a1"


def test_detect_removed_listing():
    prev = [L(article_id="a1")]
    curr = []
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "LISTING_REMOVED"


def test_detect_price_change_above_threshold():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=125000)]  # -3.85%, above 3% threshold
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert len(events) == 1
    assert events[0].kind == "PRICE_CHANGE"
    assert "130000" in events[0].detail and "125000" in events[0].detail


def test_price_change_below_threshold_ignored():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=129000)]  # -0.77%, below threshold
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert events == []


def test_unchanged_listing_produces_no_event():
    prev = [L(article_id="a1", price=130000)]
    curr = [L(article_id="a1", price=130000)]
    events = detect_changes(prev, curr, threshold_pct=3.0)
    assert events == []


def test_multiple_changes_in_one_call():
    prev = [L(article_id="a1", price=130000), L(article_id="a2", price=140000)]
    curr = [L(article_id="a1", price=120000), L(article_id="a3", price=150000)]
    # a1 dropped >3%, a2 removed, a3 new
    events = detect_changes(prev, curr, threshold_pct=3.0)
    kinds = sorted(e.kind for e in events)
    assert kinds == ["LISTING_REMOVED", "NEW_LISTING", "PRICE_CHANGE"]
```

- [ ] **Step 4.3: Run test, verify failure**

Run: `pytest tests/test_analyzer.py -v`
Expected: ImportError or ModuleNotFoundError for `src.analyzer`.

- [ ] **Step 4.4: Implement `src/analyzer.py` minimal**

```python
"""Pure analysis functions over Listing snapshots."""
from __future__ import annotations

from src.models import Event, Listing


def detect_changes(
    previous: list[Listing], current: list[Listing], threshold_pct: float
) -> list[Event]:
    prev_by_id = {l.article_id: l for l in previous}
    curr_by_id = {l.article_id: l for l in current}

    events: list[Event] = []

    for article_id, l in curr_by_id.items():
        if article_id not in prev_by_id:
            events.append(Event(
                kind="NEW_LISTING",
                complex_id=l.complex_id,
                article_id=article_id,
                detail=f"{l.size_label}㎡, {_format_price(l.price_manwon)}, {l.building} {l.floor}, {l.direction}",
                article_url=l.article_url,
            ))

    for article_id, prev_l in prev_by_id.items():
        if article_id not in curr_by_id:
            events.append(Event(
                kind="LISTING_REMOVED",
                complex_id=prev_l.complex_id,
                article_id=article_id,
                detail=f"{prev_l.size_label}㎡, {_format_price(prev_l.price_manwon)}",
                article_url=prev_l.article_url,
            ))

    for article_id, curr_l in curr_by_id.items():
        if article_id not in prev_by_id:
            continue
        prev_l = prev_by_id[article_id]
        if prev_l.price_manwon == curr_l.price_manwon:
            continue
        pct = abs(curr_l.price_manwon - prev_l.price_manwon) / prev_l.price_manwon * 100
        if pct >= threshold_pct:
            sign = "-" if curr_l.price_manwon < prev_l.price_manwon else "+"
            signed_pct = pct if curr_l.price_manwon >= prev_l.price_manwon else -pct
            events.append(Event(
                kind="PRICE_CHANGE",
                complex_id=curr_l.complex_id,
                article_id=article_id,
                detail=(
                    f"{curr_l.size_label}㎡: {prev_l.price_manwon} → "
                    f"{curr_l.price_manwon} ({signed_pct:+.1f}%)"
                ),
                article_url=curr_l.article_url,
            ))

    return events


def _format_price(manwon: int) -> str:
    """Format 만원 integer as '12억 5,000' or '5,000'."""
    eok = manwon // 10000
    rest = manwon % 10000
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}"
```

- [ ] **Step 4.5: Run tests, verify pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: 6 passed.

- [ ] **Step 4.6: Commit**

```bash
git add src/models.py src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add shared models and detect_changes analyzer"
```

---

## Task 5: `analyzer.summarize_by_size` and `top_n_lowest`

**Files:**
- Modify: `src/analyzer.py`
- Modify: `tests/test_analyzer.py`

- [ ] **Step 5.1: Add failing tests**

Append to `tests/test_analyzer.py`:
```python
from src.analyzer import summarize_by_size, top_n_lowest


def test_summarize_by_size_groups_correctly():
    listings = [
        L(article_id="a1", price=125000, size="84"),
        L(article_id="a2", price=130000, size="84"),
        L(article_id="a3", price=132000, size="84"),
        L(article_id="a4", price=180000, size="114"),
        L(article_id="a5", price=190000, size="114"),
    ]
    by_size = summarize_by_size(listings)
    assert set(by_size.keys()) == {"84", "114"}

    s84 = by_size["84"]
    assert s84.count == 3
    assert s84.min_price == 125000
    assert s84.max_price == 132000
    assert s84.avg_price == 129000  # (125000+130000+132000)/3 = 129000

    s114 = by_size["114"]
    assert s114.count == 2
    assert s114.min_price == 180000
    assert s114.avg_price == 185000


def test_summarize_empty():
    assert summarize_by_size([]) == {}


def test_top_n_lowest_returns_cheapest():
    listings = [
        L(article_id="a1", price=130000),
        L(article_id="a2", price=125000),
        L(article_id="a3", price=128000),
        L(article_id="a4", price=132000),
    ]
    top3 = top_n_lowest(listings, n=3)
    prices = [l.price_manwon for l in top3]
    assert prices == [125000, 128000, 130000]


def test_top_n_lowest_fewer_than_n():
    listings = [L(article_id="a1", price=130000)]
    assert len(top_n_lowest(listings, n=3)) == 1
```

- [ ] **Step 5.2: Run, verify failure**

Run: `pytest tests/test_analyzer.py -v`
Expected: ImportError for `summarize_by_size` / `top_n_lowest`.

- [ ] **Step 5.3: Add to `src/analyzer.py`**

Append:
```python
from src.models import SizeSummary


def summarize_by_size(listings: list[Listing]) -> dict[str, SizeSummary]:
    by_size: dict[str, list[Listing]] = {}
    for l in listings:
        by_size.setdefault(l.size_label, []).append(l)
    result = {}
    for size, items in by_size.items():
        prices = [l.price_manwon for l in items]
        result[size] = SizeSummary(
            size_label=size,
            count=len(items),
            min_price=min(prices),
            avg_price=sum(prices) // len(prices),
            max_price=max(prices),
        )
    return result


def top_n_lowest(listings: list[Listing], n: int) -> list[Listing]:
    return sorted(listings, key=lambda l: l.price_manwon)[:n]
```

- [ ] **Step 5.4: Run tests, verify pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: 10 passed.

- [ ] **Step 5.5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add summarize_by_size and top_n_lowest analyzers"
```

---

## Task 6: `naver_scraper.parse_korean_price`

**Files:**
- Create: `src/naver_scraper.py`
- Create: `tests/test_naver_parser.py`

- [ ] **Step 6.1: Write failing test**

`tests/test_naver_parser.py`:
```python
import pytest
from src.naver_scraper import parse_korean_price


@pytest.mark.parametrize("raw,expected", [
    ("5,000", 5000),
    ("8억", 80000),
    ("10억", 100000),
    ("12억 5,000", 125000),
    ("12억 5,500", 125500),
    ("1억", 10000),
    ("1억 1,234", 11234),
    ("3,500", 3500),
])
def test_parse_korean_price(raw, expected):
    assert parse_korean_price(raw) == expected


def test_parse_korean_price_empty_returns_zero():
    assert parse_korean_price("") == 0


def test_parse_korean_price_invalid_raises():
    with pytest.raises(ValueError):
        parse_korean_price("abc")
```

- [ ] **Step 6.2: Run, verify failure**

Run: `pytest tests/test_naver_parser.py -v`
Expected: ModuleNotFoundError for `src.naver_scraper`.

- [ ] **Step 6.3: Create `src/naver_scraper.py` (parser only for now)**

```python
"""Naver real-estate scraping. Network code lives here; parsing helpers too."""
from __future__ import annotations

import re


_EOK_RE = re.compile(r"^\s*(\d+)\s*억(?:\s*([\d,]+))?\s*$")


def parse_korean_price(raw: str) -> int:
    """Convert Naver price strings to 만원 units.

    Examples:
        "5,000"      -> 5000
        "8억"        -> 80000
        "12억 5,000" -> 125000
    """
    if not raw:
        return 0
    s = raw.strip()
    m = _EOK_RE.match(s)
    if m:
        eok = int(m.group(1))
        rest_str = (m.group(2) or "0").replace(",", "")
        rest = int(rest_str) if rest_str else 0
        return eok * 10000 + rest
    # No 억 — pure 만원
    plain = s.replace(",", "")
    if not plain.isdigit():
        raise ValueError(f"Unparseable price: {raw!r}")
    return int(plain)
```

- [ ] **Step 6.4: Run, verify pass**

Run: `pytest tests/test_naver_parser.py -v`
Expected: 10 passed.

- [ ] **Step 6.5: Commit**

```bash
git add src/naver_scraper.py tests/test_naver_parser.py
git commit -m "feat: parse Korean price strings to 만원 integers"
```

---

## Task 7: `naver_scraper.parse_listings` from API response

**Files:**
- Modify: `src/naver_scraper.py`
- Create: `tests/fixtures/naver_complex_response.json`
- Create: `tests/test_naver_parse_listings.py`

The real Naver endpoint pattern is `https://new.land.naver.com/api/articles/complex/{complex_id}?realEstateType=APT&tradeType=A1&page={page}`. Field names (verified): `articleList[].articleNo`, `dealOrWarrantPrc`, `area1`, `area2`, `direction`, `articleConfirmYmd`, `buildingName`, `floorInfo`.

- [ ] **Step 7.1: Create a fixture from one realistic shape**

`tests/fixtures/naver_complex_response.json`:
```json
{
  "isMoreData": false,
  "articleList": [
    {
      "articleNo": "2425167890",
      "articleName": "성복역현대홈타운",
      "tradeTypeCode": "A1",
      "tradeTypeName": "매매",
      "dealOrWarrantPrc": "12억 5,000",
      "area1": 114.0,
      "area2": 84.92,
      "direction": "남향",
      "articleConfirmYmd": "20260612",
      "buildingName": "101동",
      "floorInfo": "10/15"
    },
    {
      "articleNo": "2425167891",
      "articleName": "성복역현대홈타운",
      "tradeTypeCode": "A1",
      "dealOrWarrantPrc": "18억",
      "area1": 145.0,
      "area2": 114.7,
      "direction": "동향",
      "articleConfirmYmd": "20260610",
      "buildingName": "105동",
      "floorInfo": "5/20"
    },
    {
      "articleNo": "2425167892",
      "articleName": "성복역현대홈타운",
      "tradeTypeCode": "B1",
      "dealOrWarrantPrc": "8억",
      "area1": 84.0,
      "area2": 59.0,
      "direction": "남향",
      "articleConfirmYmd": "20260605",
      "buildingName": "102동",
      "floorInfo": "8/15"
    }
  ]
}
```

(Note: the third article is `tradeTypeCode: "B1"` — 전세 — which the parser must filter out.)

- [ ] **Step 7.2: Write failing test**

`tests/test_naver_parse_listings.py`:
```python
import json
import os
from src.naver_scraper import parse_listings


def test_parse_listings_filters_to_sale_only(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    listings = parse_listings(resp, complex_id="8692")

    # Third one is 전세, should be filtered out
    assert len(listings) == 2
    assert all(l.complex_id == "8692" for l in listings)


def test_parse_listings_extracts_fields(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    listings = parse_listings(resp, complex_id="8692")

    first = next(l for l in listings if l.article_id == "2425167890")
    assert first.price_manwon == 125000
    assert first.size_label == "85"  # round(84.92) = 85
    assert first.size_sqm == 84.92
    assert first.direction == "남향"
    assert first.building == "101동"
    assert first.floor == "10층"
    assert first.registered_ymd == "2026-06-12"
    assert first.article_url == "https://new.land.naver.com/complexes/8692?articleNo=2425167890"

    second = next(l for l in listings if l.article_id == "2425167891")
    assert second.price_manwon == 180000
    assert second.size_label == "115"  # round(114.7) = 115


def test_parse_listings_empty_response(fixture_dir):
    assert parse_listings({"articleList": []}, complex_id="8692") == []


def test_parse_listings_missing_articleList_raises():
    import pytest
    with pytest.raises(ValueError, match="articleList"):
        parse_listings({"isMoreData": False}, complex_id="8692")
```

- [ ] **Step 7.3: Run, verify failure**

Run: `pytest tests/test_naver_parse_listings.py -v`
Expected: ImportError for `parse_listings`.

- [ ] **Step 7.4: Add `parse_listings` to `src/naver_scraper.py`**

Append:
```python
from src.models import Listing


def parse_listings(response: dict, complex_id: str) -> list[Listing]:
    """Convert a Naver `/api/articles/complex/{id}` JSON response into Listings.

    Filters out non-sale (non-A1) trade types.
    """
    if "articleList" not in response:
        raise ValueError("Naver response missing 'articleList' key")

    listings: list[Listing] = []
    for item in response["articleList"]:
        if item.get("tradeTypeCode") != "A1":
            continue
        article_id = str(item["articleNo"])
        size_sqm = float(item.get("area2") or 0.0)
        size_label = str(round(size_sqm)) if size_sqm else "?"
        price_manwon = parse_korean_price(item.get("dealOrWarrantPrc", ""))
        building = item.get("buildingName", "") or ""
        floor_raw = item.get("floorInfo", "") or ""
        floor = _format_floor(floor_raw)
        direction = item.get("direction", "") or ""
        ymd_raw = item.get("articleConfirmYmd", "") or ""
        registered_ymd = _format_ymd(ymd_raw)
        url = f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}"

        listings.append(Listing(
            article_id=article_id,
            complex_id=complex_id,
            size_label=size_label,
            size_sqm=size_sqm,
            price_manwon=price_manwon,
            building=building,
            floor=floor,
            direction=direction,
            registered_ymd=registered_ymd,
            article_url=url,
        ))
    return listings


def _format_floor(raw: str) -> str:
    """'10/15' -> '10층'.  '저/15' or '저층' -> '저층'.  '' -> ''."""
    if not raw:
        return ""
    if "/" in raw:
        cur = raw.split("/", 1)[0]
        if cur.isdigit():
            return f"{cur}층"
        return f"{cur}층"
    return raw


def _format_ymd(raw: str) -> str:
    """'20260612' -> '2026-06-12'.  Anything else -> ''."""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return ""
```

- [ ] **Step 7.5: Run, verify pass**

Run: `pytest tests/test_naver_parse_listings.py -v`
Expected: 4 passed.

- [ ] **Step 7.6: Commit**

```bash
git add src/naver_scraper.py tests/fixtures/naver_complex_response.json tests/test_naver_parse_listings.py
git commit -m "feat: parse Naver complex API response into Listing models"
```

---

## Task 8: `naver_scraper.fetch_listings` with retry/backoff

**Files:**
- Modify: `src/naver_scraper.py`
- Create: `tests/test_naver_fetch.py`

- [ ] **Step 8.1: Add failing test using `respx` to mock httpx**

`tests/test_naver_fetch.py`:
```python
import json
import os
import httpx
import pytest
import respx

from src.naver_scraper import fetch_listings


@respx.mock
def test_fetch_listings_single_page(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        resp = json.load(f)

    url = "https://new.land.naver.com/api/articles/complex/8692"
    respx.get(url).mock(return_value=httpx.Response(200, json=resp))

    listings = fetch_listings("8692")

    # 3 items in fixture, 1 filtered (전세). Two pages would also be valid; this fixture has isMoreData=false
    assert len(listings) == 2


@respx.mock
def test_fetch_listings_paginates(fixture_dir):
    page1 = {
        "isMoreData": True,
        "articleList": [
            {"articleNo": "p1a", "tradeTypeCode": "A1", "dealOrWarrantPrc": "10억",
             "area1": 84.0, "area2": 59.0, "direction": "남", "articleConfirmYmd": "20260601",
             "buildingName": "101동", "floorInfo": "5/15"}
        ],
    }
    page2 = {
        "isMoreData": False,
        "articleList": [
            {"articleNo": "p2a", "tradeTypeCode": "A1", "dealOrWarrantPrc": "11억",
             "area1": 84.0, "area2": 60.0, "direction": "동", "articleConfirmYmd": "20260602",
             "buildingName": "102동", "floorInfo": "8/15"}
        ],
    }
    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [httpx.Response(200, json=page1), httpx.Response(200, json=page2)]

    listings = fetch_listings("8692")
    assert {l.article_id for l in listings} == {"p1a", "p2a"}


@respx.mock
def test_fetch_listings_retries_on_5xx(fixture_dir):
    with open(os.path.join(fixture_dir, "naver_complex_response.json"), encoding="utf-8") as f:
        ok_resp = json.load(f)

    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(200, json=ok_resp),
    ]

    listings = fetch_listings("8692")
    assert len(listings) == 2


@respx.mock
def test_fetch_listings_raises_after_max_retries():
    route = respx.get("https://new.land.naver.com/api/articles/complex/8692")
    route.side_effect = [httpx.Response(503)] * 10

    with pytest.raises(RuntimeError, match="failed"):
        fetch_listings("8692")
```

- [ ] **Step 8.2: Add `respx` to dev deps if not yet present**

Already in `pyproject.toml` from Task 1 (`respx>=0.21.0`). Skip if installed.

- [ ] **Step 8.3: Run test, verify failure**

Run: `pytest tests/test_naver_fetch.py -v`
Expected: ImportError for `fetch_listings`.

- [ ] **Step 8.4: Add `fetch_listings` to `src/naver_scraper.py`**

Append to `src/naver_scraper.py`:
```python
import time
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type
)


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_SEC = 1.0  # gentle pacing between requests
_MAX_PAGES = 20  # safety bound — should never come close


class NaverFetchError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _get_page(client: httpx.Client, complex_id: str, page: int) -> dict:
    resp = client.get(
        f"https://new.land.naver.com/api/articles/complex/{complex_id}",
        params={"realEstateType": "APT", "tradeType": "A1", "order": "rank", "page": page},
        headers={"User-Agent": _USER_AGENT, "Referer": "https://new.land.naver.com/"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_listings(complex_id: str) -> list[Listing]:
    """Fetch all sale listings for a complex, paginated, with retry."""
    all_listings: list[Listing] = []
    try:
        with httpx.Client() as client:
            for page in range(1, _MAX_PAGES + 1):
                if page > 1:
                    time.sleep(_REQUEST_DELAY_SEC)
                data = _get_page(client, complex_id, page)
                all_listings.extend(parse_listings(data, complex_id=complex_id))
                if not data.get("isMoreData"):
                    break
    except Exception as e:
        raise RuntimeError(
            f"Naver fetch failed for complex {complex_id} after retries: {e}"
        ) from e
    return all_listings
```

- [ ] **Step 8.5: Run, verify pass**

Run: `pytest tests/test_naver_fetch.py -v`
Expected: 4 passed.

(Tests may take ~30s due to `tenacity` backoff. If too slow, lower `wait_exponential` for tests only or trust the implementation.)

- [ ] **Step 8.6: Commit**

```bash
git add src/naver_scraper.py tests/test_naver_fetch.py
git commit -m "feat: paginated Naver fetch with httpx + tenacity retries"
```

---

## Task 9: `sheets_store` skeleton + tab bootstrapping

**Files:**
- Create: `src/sheets_store.py`
- Create: `tests/test_sheets_store.py`

We mock `gspread` in tests so we never hit live Sheets.

- [ ] **Step 9.1: Write failing test**

`tests/test_sheets_store.py`:
```python
from unittest.mock import MagicMock
from src.sheets_store import SheetsStore, REQUIRED_TABS


def test_ensure_tabs_creates_missing(mocker):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    # Only 'settings' exists
    existing_ws = MagicMock()
    existing_ws.title = "settings"
    fake_book.worksheets.return_value = [existing_ws]

    store = SheetsStore(sheets_id="abc", sa_info={"client_email": "x"}, client=fake_client)
    store.ensure_tabs()

    # Must have called add_worksheet for everything missing
    added_titles = {call.kwargs.get("title") or call.args[0] for call in fake_book.add_worksheet.call_args_list}
    expected_missing = set(REQUIRED_TABS) - {"settings"}
    assert added_titles == expected_missing


def test_ensure_tabs_idempotent_when_all_present(mocker):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    wsets = [MagicMock() for _ in REQUIRED_TABS]
    for ws, name in zip(wsets, REQUIRED_TABS):
        ws.title = name
    fake_book.worksheets.return_value = wsets

    store = SheetsStore(sheets_id="abc", sa_info={"client_email": "x"}, client=fake_client)
    store.ensure_tabs()

    fake_book.add_worksheet.assert_not_called()
```

- [ ] **Step 9.2: Run, verify failure**

Run: `pytest tests/test_sheets_store.py -v`
Expected: ImportError for `src.sheets_store`.

- [ ] **Step 9.3: Implement `src/sheets_store.py` skeleton**

```python
"""Google Sheets persistence layer for houseBOT."""
from __future__ import annotations

from typing import Optional

import gspread
from google.oauth2.service_account import Credentials


REQUIRED_TABS = ("settings", "latest", "history", "events", "run_log")

_HEADERS = {
    "settings": ["단지명", "단지ID", "관심평형", "활성화"],
    "latest": ["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"],
    "history": ["날짜", "단지ID", "평형", "매물수", "최저가", "평균가", "최고가"],
    "events": ["시각", "종류", "단지ID", "매물ID", "상세", "매물URL"],
    "run_log": ["시각", "모드", "결과", "단지수", "매물수", "메시지"],
}

_DEFAULT_SETTINGS_ROWS = [
    ["성복역현대홈타운", "8692", "", "TRUE"],
    ["서원마을3단지아이파크", "8425", "", "TRUE"],
]


def _new_client(sa_info: dict) -> gspread.Client:
    creds = Credentials.from_service_account_info(
        sa_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


class SheetsStore:
    def __init__(
        self,
        sheets_id: str,
        sa_info: dict,
        client: Optional[gspread.Client] = None,
    ):
        self._client = client or _new_client(sa_info)
        self._book = self._client.open_by_key(sheets_id)

    def ensure_tabs(self) -> None:
        existing = {ws.title for ws in self._book.worksheets()}
        for tab in REQUIRED_TABS:
            if tab in existing:
                continue
            ws = self._book.add_worksheet(title=tab, rows=200, cols=20)
            ws.update("A1", [_HEADERS[tab]])
            if tab == "settings":
                # Seed with the two known complexes from the design
                ws.update("A2", _DEFAULT_SETTINGS_ROWS)
```

- [ ] **Step 9.4: Run, verify pass**

Run: `pytest tests/test_sheets_store.py -v`
Expected: 2 passed.

- [ ] **Step 9.5: Commit**

```bash
git add src/sheets_store.py tests/test_sheets_store.py
git commit -m "feat: SheetsStore skeleton with tab bootstrapping"
```

---

## Task 10: `sheets_store` load apartments + settings

**Files:**
- Modify: `src/sheets_store.py`
- Modify: `tests/test_sheets_store.py`

- [ ] **Step 10.1: Add failing tests**

Append to `tests/test_sheets_store.py`:
```python
from src.config import ApartmentConfig


def _stub_book_with_settings(rows):
    """Build a fake gspread book whose 'settings' tab returns `rows` (excluding header)."""
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book

    settings_ws = MagicMock()
    settings_ws.title = "settings"
    settings_ws.get_all_values.return_value = [
        ["단지명", "단지ID", "관심평형", "활성화"],
    ] + rows
    fake_book.worksheets.return_value = [settings_ws]
    fake_book.worksheet.return_value = settings_ws
    return fake_client, fake_book


def test_load_apartments_returns_active_only():
    rows = [
        ["성복", "8692", "", "TRUE"],
        ["서원", "8425", "84, 114", "TRUE"],
        ["꺼진단지", "9999", "", "FALSE"],
    ]
    fake_client, _ = _stub_book_with_settings(rows)
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    apts = store.load_apartments()
    assert len(apts) == 2
    assert apts[0].name == "성복"
    assert apts[0].complex_id == "8692"
    assert apts[0].interested_sizes == ()
    assert apts[1].interested_sizes == ("84", "114")


def test_load_apartments_handles_empty():
    fake_client, _ = _stub_book_with_settings([])
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)
    assert store.load_apartments() == []
```

- [ ] **Step 10.2: Run, verify failure**

Run: `pytest tests/test_sheets_store.py -v`
Expected: AttributeError on `load_apartments`.

- [ ] **Step 10.3: Implement `load_apartments`**

Append to `SheetsStore` in `src/sheets_store.py`:
```python
    def load_apartments(self) -> list["ApartmentConfig"]:
        from src.config import ApartmentConfig  # local import to avoid circularity
        ws = self._book.worksheet("settings")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        result = []
        for row in rows[1:]:
            # pad row to 4 cols
            row = (row + ["", "", "", ""])[:4]
            name, complex_id, sizes_raw, active_raw = row
            if not complex_id.strip():
                continue
            active = active_raw.strip().upper() == "TRUE"
            if not active:
                continue
            sizes = tuple(s.strip() for s in sizes_raw.split(",") if s.strip())
            result.append(ApartmentConfig(
                name=name.strip(),
                complex_id=complex_id.strip(),
                interested_sizes=sizes,
                active=True,
            ))
        return result
```

- [ ] **Step 10.4: Run, verify pass**

Run: `pytest tests/test_sheets_store.py -v`
Expected: 4 passed.

- [ ] **Step 10.5: Commit**

```bash
git add src/sheets_store.py tests/test_sheets_store.py
git commit -m "feat: SheetsStore.load_apartments reads active rows from settings tab"
```

---

## Task 11: `sheets_store` latest snapshot read/write

**Files:**
- Modify: `src/sheets_store.py`
- Modify: `tests/test_sheets_store.py`

- [ ] **Step 11.1: Add failing tests**

Append to `tests/test_sheets_store.py`:
```python
from src.models import Listing


def _stub_book_with_tab(tab_name, rows_inc_header):
    fake_client = MagicMock()
    fake_book = MagicMock()
    fake_client.open_by_key.return_value = fake_book
    ws = MagicMock()
    ws.title = tab_name
    ws.get_all_values.return_value = rows_inc_header
    fake_book.worksheets.return_value = [ws]
    fake_book.worksheet.return_value = ws
    return fake_client, fake_book, ws


def _make_listing(article_id="a1", complex_id="8692", price=125000):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_save_latest_clears_and_writes():
    fake_client, _, ws = _stub_book_with_tab(
        "latest",
        [["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    listings = [_make_listing("a1"), _make_listing("a2", price=130000)]
    store.save_latest(listings, scraped_at="2026-06-13 08:30")

    ws.clear.assert_called_once()
    # The very first call after clear should write the header
    update_calls = ws.update.call_args_list
    assert update_calls[0].args[0] == "A1"
    # Then header + listing rows
    written_rows = update_calls[0].args[1]
    assert written_rows[0][0] == "단지ID"
    assert len(written_rows) == 1 + 2


def test_load_latest_parses_rows():
    fake_client, _, ws = _stub_book_with_tab(
        "latest",
        [
            ["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"],
            ["8692", "a1", "84", "125000", "101동", "10층", "남향", "2026-06-12",
             "https://new.land.naver.com/complexes/8692?articleNo=a1", "2026-06-13 08:30"],
        ],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    listings = store.load_latest()
    assert len(listings) == 1
    assert listings[0].article_id == "a1"
    assert listings[0].price_manwon == 125000
    assert listings[0].complex_id == "8692"


def test_load_latest_empty_returns_empty():
    fake_client, _, _ = _stub_book_with_tab(
        "latest",
        [["단지ID", "매물ID", "평형", "가격(만원)", "동", "층", "방향", "등록일", "매물URL", "스크랩시각"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)
    assert store.load_latest() == []
```

- [ ] **Step 11.2: Run, verify failure**

Run: `pytest tests/test_sheets_store.py -v`
Expected: AttributeError on `save_latest` / `load_latest`.

- [ ] **Step 11.3: Implement `save_latest` and `load_latest`**

Append to `SheetsStore`:
```python
    def save_latest(self, listings: list["Listing"], scraped_at: str) -> None:
        ws = self._book.worksheet("latest")
        ws.clear()
        header = _HEADERS["latest"]
        rows = [header]
        for l in listings:
            rows.append([
                l.complex_id, l.article_id, l.size_label, str(l.price_manwon),
                l.building, l.floor, l.direction, l.registered_ymd,
                l.article_url, scraped_at,
            ])
        ws.update("A1", rows)

    def load_latest(self) -> list["Listing"]:
        from src.models import Listing
        ws = self._book.worksheet("latest")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        result = []
        for row in rows[1:]:
            row = (row + [""] * 10)[:10]
            complex_id, article_id, size, price_str, building, floor, direction, ymd, url, _scraped = row
            if not article_id.strip():
                continue
            try:
                price = int(price_str)
            except ValueError:
                continue
            result.append(Listing(
                article_id=article_id, complex_id=complex_id, size_label=size,
                size_sqm=0.0, price_manwon=price, building=building, floor=floor,
                direction=direction, registered_ymd=ymd, article_url=url,
            ))
        return result
```

(Note: `size_sqm` is not round-tripped — analyzer never uses it after parsing.)

- [ ] **Step 11.4: Run, verify pass**

Run: `pytest tests/test_sheets_store.py -v`
Expected: 7 passed.

- [ ] **Step 11.5: Commit**

```bash
git add src/sheets_store.py tests/test_sheets_store.py
git commit -m "feat: SheetsStore save_latest and load_latest for snapshot round-trip"
```

---

## Task 12: `sheets_store` append history, events, run_log

**Files:**
- Modify: `src/sheets_store.py`
- Modify: `tests/test_sheets_store.py`

- [ ] **Step 12.1: Add failing tests**

Append to `tests/test_sheets_store.py`:
```python
from src.models import Event, SizeSummary


def test_append_history_writes_one_row_per_size():
    fake_client, _, ws = _stub_book_with_tab(
        "history",
        [["날짜", "단지ID", "평형", "매물수", "최저가", "평균가", "최고가"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    summaries = {
        "84": SizeSummary("84", count=3, min_price=125000, avg_price=129000, max_price=132000),
        "114": SizeSummary("114", count=2, min_price=180000, avg_price=185000, max_price=190000),
    }
    store.append_history(date="2026-06-13", complex_id="8692", summaries=summaries)

    ws.append_rows.assert_called_once()
    rows_written = ws.append_rows.call_args.args[0]
    assert len(rows_written) == 2


def test_append_events_writes_each_event():
    fake_client, _, ws = _stub_book_with_tab(
        "events",
        [["시각", "종류", "단지ID", "매물ID", "상세", "매물URL"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    events = [
        Event(kind="NEW_LISTING", complex_id="8692", article_id="a1",
              detail="84㎡, 12억", article_url="https://x/a1"),
        Event(kind="PRICE_CHANGE", complex_id="8692", article_id="a2",
              detail="84㎡: 130000 → 125000", article_url="https://x/a2"),
    ]
    store.append_events(events, when="2026-06-13 10:30")

    ws.append_rows.assert_called_once()
    rows = ws.append_rows.call_args.args[0]
    assert len(rows) == 2
    assert rows[0][1] == "NEW_LISTING"


def test_append_run_log_writes_one_row():
    fake_client, _, ws = _stub_book_with_tab(
        "run_log",
        [["시각", "모드", "결과", "단지수", "매물수", "메시지"]],
    )
    store = SheetsStore("abc", {"client_email": "x"}, client=fake_client)

    store.append_run_log(when="2026-06-13 08:30", mode="daily",
                         result="SUCCESS", complex_count=2, listing_count=17, message="")

    ws.append_row.assert_called_once()
    row = ws.append_row.call_args.args[0]
    assert row[1] == "daily" and row[2] == "SUCCESS"
```

- [ ] **Step 12.2: Run, verify failure**

Run: `pytest tests/test_sheets_store.py -v`
Expected: AttributeError on `append_history` / `append_events` / `append_run_log`.

- [ ] **Step 12.3: Implement the three appenders**

Append to `SheetsStore`:
```python
    def append_history(
        self, date: str, complex_id: str, summaries: dict[str, "SizeSummary"]
    ) -> None:
        from src.models import SizeSummary  # noqa
        ws = self._book.worksheet("history")
        rows = [
            [date, complex_id, s.size_label, s.count, s.min_price, s.avg_price, s.max_price]
            for s in summaries.values()
        ]
        if rows:
            ws.append_rows(rows)

    def append_events(self, events: list["Event"], when: str) -> None:
        if not events:
            return
        ws = self._book.worksheet("events")
        rows = [
            [when, e.kind, e.complex_id, e.article_id, e.detail, e.article_url]
            for e in events
        ]
        ws.append_rows(rows)

    def append_run_log(
        self, when: str, mode: str, result: str,
        complex_count: int, listing_count: int, message: str = ""
    ) -> None:
        ws = self._book.worksheet("run_log")
        ws.append_row([when, mode, result, complex_count, listing_count, message])
```

- [ ] **Step 12.4: Run, verify pass**

Run: `pytest tests/test_sheets_store.py -v`
Expected: 10 passed.

- [ ] **Step 12.5: Commit**

```bash
git add src/sheets_store.py tests/test_sheets_store.py
git commit -m "feat: SheetsStore append_history, append_events, append_run_log"
```

---

## Task 13: `telegram_notifier.format_daily_summary`

**Files:**
- Create: `src/telegram_notifier.py`
- Create: `tests/test_notifier_format.py`

We use Telegram HTML parse mode with `<a href="...">text</a>` links.

- [ ] **Step 13.1: Write failing test**

`tests/test_notifier_format.py`:
```python
from src.models import Listing, Event, SizeSummary
from src.config import ApartmentConfig
from src.telegram_notifier import format_daily_summary, ComplexReport


def _listing(article_id="a1", complex_id="8692", price=125000, size="84"):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label=size,
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


def test_format_daily_summary_includes_complex_name_with_link():
    apt = ApartmentConfig(name="성복역현대홈타운", complex_id="8692", interested_sizes=(), active=True)
    report = ComplexReport(
        apartment=apt,
        listings_today=[_listing("a1"), _listing("a2", price=130000)],
        count_today=2,
        count_yesterday=2,
        size_summaries={"84": SizeSummary("84", 2, 125000, 127500, 130000)},
        new_listings=[],
        price_changes=[],
        top_lowest=[_listing("a1")],
    )

    text = format_daily_summary(
        date="2026-06-14", reports=[report],
        sheets_url="https://docs.google.com/spreadsheets/d/abc/edit",
    )

    assert "houseBOT" in text
    assert "2026-06-14" in text
    # Complex name appears as a hyperlink
    assert '<a href="https://new.land.naver.com/complexes/8692">성복역현대홈타운</a>' in text
    # Size summary appears
    assert "84㎡" in text
    # Sheets link present
    assert '<a href="https://docs.google.com/spreadsheets/d/abc/edit">' in text


def test_format_daily_summary_renders_new_and_price_changes():
    apt = ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True)
    new_l = _listing("a3", price=148000)
    price_change_event = Event(
        kind="PRICE_CHANGE", complex_id="8692", article_id="a1",
        detail="84㎡: 130000 → 125000 (-3.8%)",
        article_url="https://new.land.naver.com/complexes/8692?articleNo=a1",
    )
    report = ComplexReport(
        apartment=apt,
        listings_today=[_listing("a1"), new_l],
        count_today=2, count_yesterday=1,
        size_summaries={"84": SizeSummary("84", 2, 125000, 136500, 148000)},
        new_listings=[new_l],
        price_changes=[price_change_event],
        top_lowest=[_listing("a1")],
    )
    text = format_daily_summary("2026-06-14", [report], "https://x")

    assert "🆕" in text
    assert '<a href="' + new_l.article_url + '">' in text
    assert "📉" in text
    assert "-3.8%" in text
```

- [ ] **Step 13.2: Run, verify failure**

Run: `pytest tests/test_notifier_format.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 13.3: Create `src/telegram_notifier.py`**

```python
"""Telegram message formatting and sending."""
from __future__ import annotations

from dataclasses import dataclass

from src.config import ApartmentConfig
from src.models import Event, Listing, SizeSummary


@dataclass(frozen=True)
class ComplexReport:
    apartment: ApartmentConfig
    listings_today: list[Listing]
    count_today: int
    count_yesterday: int
    size_summaries: dict[str, SizeSummary]
    new_listings: list[Listing]
    price_changes: list[Event]
    top_lowest: list[Listing]


def _format_price(manwon: int) -> str:
    eok = manwon // 10000
    rest = manwon % 10000
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}"


def _link(url: str, text: str) -> str:
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return f'<a href="{url}">{safe}</a>'


def _format_listing_line(l: Listing) -> str:
    parts = [
        f"{l.size_label}㎡",
        _format_price(l.price_manwon),
        f"{l.building} {l.floor}".strip(),
        l.direction,
    ]
    inner = ", ".join(p for p in parts if p)
    return _link(l.article_url, inner)


def format_daily_summary(
    date: str, reports: list[ComplexReport], sheets_url: str
) -> str:
    lines: list[str] = []
    lines.append(f"🏠 <b>houseBOT 일일 요약</b> ({date})")
    lines.append("")

    for r in reports:
        complex_url = f"https://new.land.naver.com/complexes/{r.apartment.complex_id}"
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(f"📍 {_link(complex_url, r.apartment.name)}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        diff = r.count_today - r.count_yesterday
        diff_str = (f"+{diff}" if diff > 0 else f"{diff}") if diff != 0 else "변동 없음"
        lines.append(f"📊 매물 수: {r.count_today}건 (어제 {r.count_yesterday}건, {diff_str})")
        lines.append("")
        if r.size_summaries:
            lines.append("💰 평형별 시세")
            for size, s in sorted(r.size_summaries.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999):
                lines.append(
                    f" • {size}㎡  최저 {_format_price(s.min_price)} / "
                    f"평균 {_format_price(s.avg_price)} ({s.count}건)"
                )
            lines.append("")
        if r.new_listings:
            lines.append(f"🆕 신규 매물 ({len(r.new_listings)}건)")
            for l in r.new_listings:
                lines.append(f" • {_format_listing_line(l)}")
            lines.append("")
        if r.price_changes:
            lines.append(f"📉 가격 변동 ({len(r.price_changes)}건)")
            for e in r.price_changes:
                lines.append(f" • {_link(e.article_url, e.detail)}")
            lines.append("")
        if r.top_lowest:
            lines.append("🏷 최저가 TOP")
            for i, l in enumerate(r.top_lowest, 1):
                lines.append(f" {i}. {_format_listing_line(l)}")
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 {_link(sheets_url, '전체 추이 보기 → Google Sheets')}")

    return "\n".join(lines)
```

- [ ] **Step 13.4: Run, verify pass**

Run: `pytest tests/test_notifier_format.py -v`
Expected: 2 passed.

- [ ] **Step 13.5: Commit**

```bash
git add src/telegram_notifier.py tests/test_notifier_format.py
git commit -m "feat: format_daily_summary builds HTML Telegram message with links"
```

---

## Task 14: `format_light_check` and `format_error`

**Files:**
- Modify: `src/telegram_notifier.py`
- Modify: `tests/test_notifier_format.py`

- [ ] **Step 14.1: Add failing tests**

Append to `tests/test_notifier_format.py`:
```python
from src.telegram_notifier import format_light_check, format_error, ComplexChanges


def test_format_light_check_skipped_when_no_changes():
    """Caller should not call format_light_check if no changes; assert it raises."""
    import pytest
    with pytest.raises(ValueError, match="no changes"):
        format_light_check(time="12:30", complex_changes=[])


def test_format_light_check_renders_new_and_price():
    apt = ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True)
    new_l = _listing("a3", price=130000)
    price_event = Event(
        kind="PRICE_CHANGE", complex_id="8692", article_id="a1",
        detail="145㎡: 195000 → 188000 (-3.6%)",
        article_url="https://new.land.naver.com/complexes/8692?articleNo=a1",
    )
    changes = ComplexChanges(apartment=apt, new_listings=[new_l], price_changes=[price_event])
    text = format_light_check("12:30", [changes])

    assert "🔔" in text
    assert "12:30" in text
    assert "성복" in text
    assert "신규 매물 1건" in text
    assert "가격 변동 1건" in text
    assert "-3.6%" in text


def test_format_error_renders_message():
    text = format_error("네이버 API 구조 변경 감지\n단지: 성복 (8692)\n원인: 'dealPrice' 누락")
    assert "🚨" in text
    assert "성복" in text
```

- [ ] **Step 14.2: Run, verify failure**

Run: `pytest tests/test_notifier_format.py -v`
Expected: ImportError for `format_light_check` / `ComplexChanges` / `format_error`.

- [ ] **Step 14.3: Append to `src/telegram_notifier.py`**

```python
@dataclass(frozen=True)
class ComplexChanges:
    apartment: ApartmentConfig
    new_listings: list[Listing]
    price_changes: list[Event]


def format_light_check(time: str, complex_changes: list[ComplexChanges]) -> str:
    if not complex_changes or all(
        not c.new_listings and not c.price_changes for c in complex_changes
    ):
        raise ValueError("format_light_check called with no changes — caller should skip send")

    lines = [f"🔔 <b>변동 알림</b> ({time})", ""]
    for c in complex_changes:
        if not c.new_listings and not c.price_changes:
            continue
        complex_url = f"https://new.land.naver.com/complexes/{c.apartment.complex_id}"
        lines.append(f"📍 {_link(complex_url, c.apartment.name)}")
        if c.new_listings:
            lines.append(f"🆕 신규 매물 {len(c.new_listings)}건")
            for l in c.new_listings:
                lines.append(f" • {_format_listing_line(l)}")
        if c.price_changes:
            lines.append(f"📉 가격 변동 {len(c.price_changes)}건")
            for e in c.price_changes:
                lines.append(f" • {_link(e.article_url, e.detail)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_error(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"🚨 <b>houseBOT 에러</b>\n\n{safe}"
```

- [ ] **Step 14.4: Run, verify pass**

Run: `pytest tests/test_notifier_format.py -v`
Expected: 5 passed.

- [ ] **Step 14.5: Commit**

```bash
git add src/telegram_notifier.py tests/test_notifier_format.py
git commit -m "feat: format_light_check and format_error message builders"
```

---

## Task 15: `telegram_notifier.send_message`

**Files:**
- Modify: `src/telegram_notifier.py`
- Create: `tests/test_notifier_send.py`

- [ ] **Step 15.1: Write failing test**

`tests/test_notifier_send.py`:
```python
import httpx
import pytest
import respx
from src.telegram_notifier import send_message


@respx.mock
def test_send_message_posts_html(capsys):
    route = respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    send_message(token="123:abc", chat_id="999", html="<b>hi</b>", dry_run=False)
    assert route.called
    body = route.calls[0].request.read().decode()
    assert "parse_mode=HTML" in body or "parse_mode" in body
    assert "999" in body


@respx.mock
def test_send_message_dry_run_skips_http(capsys):
    route = respx.post("https://api.telegram.org/bot123:abc/sendMessage")
    send_message(token="123:abc", chat_id="999", html="<b>hi</b>", dry_run=True)
    assert not route.called
    out = capsys.readouterr().out
    assert "[DRY_RUN] Telegram" in out
    assert "hi" in out


@respx.mock
def test_send_message_raises_on_telegram_error():
    respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request"})
    )
    with pytest.raises(RuntimeError, match="Telegram"):
        send_message(token="123:abc", chat_id="999", html="x", dry_run=False)
```

- [ ] **Step 15.2: Run, verify failure**

Run: `pytest tests/test_notifier_send.py -v`
Expected: ImportError for `send_message`.

- [ ] **Step 15.3: Append `send_message` to `src/telegram_notifier.py`**

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_telegram(token: str, chat_id: str, html: str) -> None:
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=15.0,
    )
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise RuntimeError(f"Telegram send failed: {resp.status_code} {resp.text}")


def send_message(token: str, chat_id: str, html: str, dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY_RUN] Telegram message would be:")
        print(html)
        return
    _post_telegram(token, chat_id, html)
```

- [ ] **Step 15.4: Run, verify pass**

Run: `pytest tests/test_notifier_send.py -v`
Expected: 3 passed.

- [ ] **Step 15.5: Run full test suite**

Run: `pytest -v`
Expected: All tests pass (~30+ tests across files).

- [ ] **Step 15.6: Commit**

```bash
git add src/telegram_notifier.py tests/test_notifier_send.py
git commit -m "feat: send_message wraps Telegram Bot API with retry and dry-run"
```

---

## Task 16: `run_daily.py` orchestration

**Files:**
- Create: `src/run_daily.py`
- Create: `tests/test_run_daily.py`

- [ ] **Step 16.1: Write failing integration-style test**

`tests/test_run_daily.py`:
```python
from unittest.mock import MagicMock, patch
from src.models import Listing
from src.config import ApartmentConfig, Settings


def _settings(dry=False):
    return Settings(
        telegram_bot_token="tok", telegram_chat_id="cid",
        sheets_id="sid", google_sa_info={"client_email": "x"},
        dry_run=dry,
    )


def _make_listing(article_id, complex_id, price):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


@patch("src.run_daily.send_message")
@patch("src.run_daily.fetch_listings")
@patch("src.run_daily.SheetsStore")
@patch("src.run_daily.load_settings")
def test_run_daily_happy_path(mock_load_settings, MockStore, mock_fetch, mock_send):
    mock_load_settings.return_value = _settings(dry=False)

    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 130000)]

    mock_fetch.return_value = [
        _make_listing("a1", "8692", 125000),  # price drop
        _make_listing("a2", "8692", 140000),  # new listing
    ]

    from src.run_daily import main
    main()

    store.ensure_tabs.assert_called_once()
    store.save_latest.assert_called_once()
    store.append_history.assert_called_once()
    store.append_events.assert_called_once()
    store.append_run_log.assert_called_once()
    mock_send.assert_called_once()
    # The sent message should contain the complex name
    sent_text = mock_send.call_args.kwargs.get("html") or mock_send.call_args.args[2]
    assert "성복" in sent_text


@patch("src.run_daily.send_message")
@patch("src.run_daily.fetch_listings")
@patch("src.run_daily.SheetsStore")
@patch("src.run_daily.load_settings")
def test_run_daily_continues_on_single_complex_failure(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="A", complex_id="111", interested_sizes=(), active=True),
        ApartmentConfig(name="B", complex_id="222", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = []

    def fetch_side_effect(complex_id):
        if complex_id == "111":
            raise RuntimeError("Naver fetch failed for complex 111")
        return [_make_listing("a1", "222", 100000)]

    mock_fetch.side_effect = fetch_side_effect

    from src.run_daily import main
    main()  # should NOT raise

    # Telegram is still sent (with the successful complex)
    mock_send.assert_called_once()
```

- [ ] **Step 16.2: Run, verify failure**

Run: `pytest tests/test_run_daily.py -v`
Expected: ImportError for `src.run_daily`.

- [ ] **Step 16.3: Implement `src/run_daily.py`**

```python
"""Daily summary entrypoint — runs at 08:30 KST via GitHub Actions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.analyzer import detect_changes, summarize_by_size, top_n_lowest
from src.config import load_settings
from src.naver_scraper import fetch_listings
from src.sheets_store import SheetsStore
from src.telegram_notifier import (
    ComplexReport, format_daily_summary, format_error, send_message,
)


KST = timezone(timedelta(hours=9))
PRICE_CHANGE_THRESHOLD_PCT = 3.0
TOP_N = 3


def main() -> None:
    settings = load_settings()
    store = SheetsStore(settings.sheets_id, settings.google_sa_info)
    store.ensure_tabs()
    apartments = store.load_apartments()
    if not apartments:
        print("No active apartments — nothing to do.")
        return

    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d")
    when_str = now.strftime("%Y-%m-%d %H:%M")

    previous_all = store.load_latest()
    previous_by_complex: dict[str, list] = {}
    for l in previous_all:
        previous_by_complex.setdefault(l.complex_id, []).append(l)

    reports: list[ComplexReport] = []
    all_today: list = []
    all_events: list = []
    failures: list[str] = []

    for apt in apartments:
        try:
            today_listings = fetch_listings(apt.complex_id)
        except Exception as e:
            failures.append(f"{apt.name} ({apt.complex_id}): {e}")
            continue

        prev = previous_by_complex.get(apt.complex_id, [])
        events = detect_changes(prev, today_listings, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)
        summaries = summarize_by_size(today_listings)
        store.append_history(today_str, apt.complex_id, summaries)

        all_today.extend(today_listings)
        all_events.extend(events)

        new_listings = [
            l for l in today_listings
            if any(e.kind == "NEW_LISTING" and e.article_id == l.article_id for e in events)
        ]
        price_events = [e for e in events if e.kind == "PRICE_CHANGE"]
        reports.append(ComplexReport(
            apartment=apt,
            listings_today=today_listings,
            count_today=len(today_listings),
            count_yesterday=len(prev),
            size_summaries=summaries,
            new_listings=new_listings,
            price_changes=price_events,
            top_lowest=top_n_lowest(today_listings, TOP_N),
        ))

    if all_today:
        store.save_latest(all_today, scraped_at=when_str)
    if all_events:
        store.append_events(all_events, when=when_str)

    sheets_url = f"https://docs.google.com/spreadsheets/d/{settings.sheets_id}/edit"
    if reports:
        msg = format_daily_summary(today_str, reports, sheets_url)
        send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            html=msg,
            dry_run=settings.dry_run,
        )

    if failures:
        send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            html=format_error("일부 단지 수집 실패:\n" + "\n".join(failures)),
            dry_run=settings.dry_run,
        )

    store.append_run_log(
        when=when_str, mode="daily",
        result="SUCCESS" if not failures else "PARTIAL",
        complex_count=len(reports), listing_count=len(all_today),
        message=" | ".join(failures) if failures else "",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 16.4: Run tests, verify pass**

Run: `pytest tests/test_run_daily.py -v`
Expected: 2 passed.

- [ ] **Step 16.5: Commit**

```bash
git add src/run_daily.py tests/test_run_daily.py
git commit -m "feat: run_daily orchestrates full daily summary flow"
```

---

## Task 17: `run_check.py` orchestration (light check)

**Files:**
- Create: `src/run_check.py`
- Create: `tests/test_run_check.py`

- [ ] **Step 17.1: Write failing test**

`tests/test_run_check.py`:
```python
from unittest.mock import MagicMock, patch
from src.config import ApartmentConfig, Settings
from src.models import Listing


def _settings():
    return Settings(
        telegram_bot_token="tok", telegram_chat_id="cid", sheets_id="sid",
        google_sa_info={"client_email": "x"}, dry_run=False,
    )


def _make_listing(article_id, complex_id, price):
    return Listing(
        article_id=article_id, complex_id=complex_id, size_label="84",
        size_sqm=84.5, price_manwon=price, building="101동", floor="10층",
        direction="남향", registered_ymd="2026-06-12",
        article_url=f"https://new.land.naver.com/complexes/{complex_id}?articleNo={article_id}",
    )


@patch("src.run_check.send_message")
@patch("src.run_check.fetch_listings")
@patch("src.run_check.SheetsStore")
@patch("src.run_check.load_settings")
def test_run_check_silent_when_no_changes(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 125000)]
    mock_fetch.return_value = [_make_listing("a1", "8692", 125000)]  # identical

    from src.run_check import main
    main()

    mock_send.assert_not_called()
    store.save_latest.assert_not_called()  # no change → no overwrite needed


@patch("src.run_check.send_message")
@patch("src.run_check.fetch_listings")
@patch("src.run_check.SheetsStore")
@patch("src.run_check.load_settings")
def test_run_check_sends_when_new_listing(
    mock_load_settings, MockStore, mock_fetch, mock_send
):
    mock_load_settings.return_value = _settings()
    store = MagicMock()
    MockStore.return_value = store
    store.load_apartments.return_value = [
        ApartmentConfig(name="성복", complex_id="8692", interested_sizes=(), active=True),
    ]
    store.load_latest.return_value = [_make_listing("a1", "8692", 125000)]
    mock_fetch.return_value = [
        _make_listing("a1", "8692", 125000),
        _make_listing("a2", "8692", 130000),  # new
    ]

    from src.run_check import main
    main()

    mock_send.assert_called_once()
    store.save_latest.assert_called_once()
    store.append_events.assert_called_once()
```

- [ ] **Step 17.2: Run, verify failure**

Run: `pytest tests/test_run_check.py -v`
Expected: ImportError.

- [ ] **Step 17.3: Implement `src/run_check.py`**

```python
"""Light change check entrypoint — runs every 2 hours 09-21 KST via GitHub Actions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.analyzer import detect_changes
from src.config import load_settings
from src.naver_scraper import fetch_listings
from src.sheets_store import SheetsStore
from src.telegram_notifier import (
    ComplexChanges, format_error, format_light_check, send_message,
)


KST = timezone(timedelta(hours=9))
PRICE_CHANGE_THRESHOLD_PCT = 3.0


def main() -> None:
    settings = load_settings()
    store = SheetsStore(settings.sheets_id, settings.google_sa_info)
    store.ensure_tabs()
    apartments = store.load_apartments()
    if not apartments:
        return

    now = datetime.now(KST)
    when_str = now.strftime("%Y-%m-%d %H:%M")
    time_str = now.strftime("%H:%M")

    previous_all = store.load_latest()
    prev_by_complex: dict[str, list] = {}
    for l in previous_all:
        prev_by_complex.setdefault(l.complex_id, []).append(l)

    changes_per_complex: list[ComplexChanges] = []
    all_today: list = []
    all_events: list = []
    failures: list[str] = []

    for apt in apartments:
        try:
            today_listings = fetch_listings(apt.complex_id)
        except Exception as e:
            failures.append(f"{apt.name} ({apt.complex_id}): {e}")
            continue
        all_today.extend(today_listings)
        prev = prev_by_complex.get(apt.complex_id, [])
        events = detect_changes(prev, today_listings, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)
        new_event_ids = {e.article_id for e in events if e.kind == "NEW_LISTING"}
        new_listings = [l for l in today_listings if l.article_id in new_event_ids]
        price_events = [e for e in events if e.kind == "PRICE_CHANGE"]
        if new_listings or price_events:
            changes_per_complex.append(ComplexChanges(
                apartment=apt, new_listings=new_listings, price_changes=price_events,
            ))
            all_events.extend([e for e in events if e.kind in ("NEW_LISTING", "PRICE_CHANGE")])

    has_changes = bool(changes_per_complex)

    if has_changes:
        store.save_latest(all_today, scraped_at=when_str)
        store.append_events(all_events, when=when_str)
        msg = format_light_check(time_str, changes_per_complex)
        send_message(
            token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id,
            html=msg, dry_run=settings.dry_run,
        )

    if failures:
        send_message(
            token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id,
            html=format_error("일부 단지 수집 실패:\n" + "\n".join(failures)),
            dry_run=settings.dry_run,
        )

    store.append_run_log(
        when=when_str, mode="check",
        result="SUCCESS" if not failures else "PARTIAL",
        complex_count=len(apartments), listing_count=len(all_today),
        message="changes" if has_changes else "no-changes",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 17.4: Run, verify pass**

Run: `pytest tests/test_run_check.py -v`
Expected: 2 passed.

- [ ] **Step 17.5: Run full suite**

Run: `pytest -v`
Expected: All tests pass (~35+ tests).

- [ ] **Step 17.6: Commit**

```bash
git add src/run_check.py tests/test_run_check.py
git commit -m "feat: run_check orchestrates 2-hour light change check"
```

---

## Task 18: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/daily-summary.yml`
- Create: `.github/workflows/light-check.yml`

GitHub Actions cron uses UTC. KST = UTC+9, so:
- 08:30 KST = 23:30 UTC (previous day)
- 09:00–21:00 KST every 2h = 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00 UTC

- [ ] **Step 18.1: Create daily workflow**

`.github/workflows/daily-summary.yml`:
```yaml
name: Daily Summary

on:
  schedule:
    - cron: "30 23 * * *"  # 08:30 KST every day
  workflow_dispatch:        # also runnable manually from the Actions tab

concurrency:
  group: housebot-daily
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run daily summary
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
          GOOGLE_SHEETS_ID:   ${{ secrets.GOOGLE_SHEETS_ID }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          DRY_RUN: "false"
        run: python -m src.run_daily
```

- [ ] **Step 18.2: Create light-check workflow**

`.github/workflows/light-check.yml`:
```yaml
name: Light Check

on:
  schedule:
    # 09:00, 11:00, 13:00, 15:00, 17:00, 19:00, 21:00 KST
    # → 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00 UTC
    - cron: "0 0,2,4,6,8,10,12 * * *"
  workflow_dispatch:

concurrency:
  group: housebot-check
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run light check
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
          GOOGLE_SHEETS_ID:   ${{ secrets.GOOGLE_SHEETS_ID }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          DRY_RUN: "false"
        run: python -m src.run_check
```

- [ ] **Step 18.3: Commit**

```bash
git add .github/workflows/
git commit -m "ci: add daily-summary and light-check GitHub Actions cron workflows"
```

---

## Task 19: Push to GitHub and configure Secrets (manual)

This task has no code — it configures the deployment surface.

- [ ] **Step 19.1: Create a private GitHub repo**

1. github.com → "New repository"
2. Name: `houseBOT` (or any name)
3. **Private** (recommended — contains config that hints at your interests)
4. No README/license — local repo already has files

- [ ] **Step 19.2: Push local repo**

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/houseBOT.git
git push -u origin main
```

- [ ] **Step 19.3: Add Secrets**

In the repo: Settings → Secrets and variables → Actions → New repository secret. Add four:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your chat ID |
| `GOOGLE_SHEETS_ID` | The sheet ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Entire compacted JSON (one line) from `google-sa.json` |

- [ ] **Step 19.4: Trigger workflows manually for first verification**

1. Actions tab → "Daily Summary" workflow → "Run workflow" → Run
2. Watch the run; verify Telegram receives the summary and Sheets gets new rows
3. Same for "Light Check"

If anything fails, check the run logs — error usually points to wrong secret or sheet not shared with the service account email.

---

## Task 20: Local DRY_RUN integration verification

**Files:**
- (no code changes — local test only)

- [ ] **Step 20.1: Verify the `.env` file is populated**

```bash
type .env
```
(Windows) or `cat .env` — confirm all 5 keys have real values.

- [ ] **Step 20.2: Load env and run daily flow in dry-run mode**

PowerShell:
```powershell
$env:DRY_RUN="true"
Get-Content .env | ForEach-Object {
  if ($_ -match "^([^=]+)=(.*)$") { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
python -m src.run_daily
```

Bash:
```bash
export $(grep -v '^#' .env | xargs -d '\n')
export DRY_RUN=true
python -m src.run_daily
```

Expected: Console prints `[DRY_RUN] Telegram message would be:` followed by the full HTML message. No actual Telegram send. Sheets writes still happen (this is intended — gives you real data to inspect).

- [ ] **Step 20.3: Verify Google Sheet looks correct**

Open the sheet in browser. Confirm:
- `settings` tab has the 2 complexes
- `latest` tab has one row per current sale listing
- `history` tab has one row per (date, complex, size)
- `events` tab may have NEW_LISTING rows
- `run_log` tab has a `daily SUCCESS` row

- [ ] **Step 20.4: Run light check in dry-run mode**

```bash
DRY_RUN=true python -m src.run_check
```

Expected: Either silent (no changes) or prints `[DRY_RUN] Telegram` message. Sheets `latest` may be re-written; `run_log` gets a `check` row.

- [ ] **Step 20.5: Final test pass + commit**

```bash
pytest -v
```
Expected: All tests pass.

If any final tweaks were made, commit them:
```bash
git add -A
git commit -m "chore: minor adjustments after local dry-run verification"
```

---

## Done — what's next

After this plan executes you have:
- Working bot deployed to GitHub Actions
- Sheets accumulating history
- Telegram receiving daily 08:30 summary + light-check alerts

Possible follow-ups (each its own future plan):
- Custom Telegram bot commands (`/today`, `/pause`)
- Email backup notification if Telegram fails
- Add 전세/월세 tracking
- Hourly check for hot deals only (e.g. new listing < threshold)
- Trend chart image attached to summaries
