# houseBOT — 프로젝트 안내 (Claude용)

> 이 파일은 세션 시작 시 자동으로 읽힙니다. 더 자세한 내용은 **`히스토리.md`**를 보세요.

## 사용자
- 이름: **서호님** (Seoho). 한국어로 대화.
- 작업 스타일: **다단계 작업은 끝까지 다 실행하고 한 번에 보고.** 중간중간 "이거 할까요?" 확인 최소화.
- 비개발자에 가까움 → 설명은 **쉽고 간단하게**. 명령어는 복붙 가능하게 통째로.

## 이 프로젝트가 하는 일
네이버 부동산 **매물 알림 봇**. 정해진 시간에 매물을 수집해 **텔레그램**으로 보내고 **Google Sheets**에 기록.

- **추적 단지**: 성복역현대홈타운(`8692`), 서원마을3단지아이파크(`8425`) — 거래유형 매매, 평형 전체
- **알림 시간** (Windows 작업 스케줄러로 실행)
  - 매일 **08:30** — 풀 요약 (`run_daily`)
  - **09/11/13/15/17/19/21시** — 변동 체크. 변동 없어도 현재 스냅샷 항상 발송 (`run_check`)
- **채널**: 텔레그램 `@houseoho_bot` / **저장**: Google Sheets `HouseBOT`

## 구조 (src/)
`config` · `models` · `analyzer` · `naver_scraper` · `sheets_store` · `telegram_notifier` · `run_daily` · `run_check`
- 네이버 수집은 **Playwright 헤드리스 브라우저** 사용 (그냥 HTTP면 401/차단). → `python -m playwright install chromium` 필수.
- 메시지는 텔레그램 **HTML parse_mode**. 평형별 시세 밑 매물 리스트는 `<blockquote expandable>`(접이식) 사용.

## 자주 쓰는 명령
```bash
# 설치 (Python 3.11+)
pip install -e ".[dev]"
python -m playwright install chromium

# 테스트 (현재 61개 통과)
python -m pytest -q

# 수동 발송 테스트 (.env 로드 래퍼)
powershell -ExecutionPolicy Bypass -File scripts\run_check.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1

# 작업 스케줄러 등록 (여러 PC면 시차 두기)
powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1 -DailyAt "08:32" -CheckOffsetMinutes 2
```

## 비밀 파일 (git에 없음 — 수동 배치 필요)
| 파일 | 용도 |
|---|---|
| `.env` | 텔레그램 토큰/챗ID, 시트ID, SA JSON 경로 등 |
| `google-sa.json` | Google 서비스 계정 키 (프로젝트 폴더 **밖**에 두는 걸 권장) |

새 PC 셋업 = `git clone` + 이 2개 파일 배치 + 위 설치 명령 + 스케줄러 등록.

## 운영 팁
- 단지 추가/제거·일시정지: Google Sheets `settings` 탭 직접 편집 (코드 수정 불필요).
- 알림이 안 오면: ① PC가 그 시각에 켜져 있었는지(절전이면 그 회차 스킵) ② 네이버 IP 일시 차단(몇 시간~하루면 풀림) ③ `run_log` 탭 마지막 row 확인.
- 트러블슈팅 상세는 `히스토리.md` §7.
