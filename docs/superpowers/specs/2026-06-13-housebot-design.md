# houseBOT 설계 문서

- **작성일**: 2026-06-13
- **작성자**: 서호 (with Claude)
- **상태**: 초안

## 1. 프로젝트 개요

### 1.1 목적
관심 아파트 단지의 매물 동향(가격, 신규/사라진 매물, 평형별 시세 등)을 자동 수집하여, 매일 아침과 일중 변동 발생 시 Telegram으로 요약 알림을 받는 개인용 부동산 모니터링 봇.

### 1.2 사용자
- 서호 (1인 운영, 비상업적 개인 사용)

### 1.3 추적 대상 (초기)
| 단지명 | 네이버 단지 ID | 관심 평형 |
|---|---|---|
| 성복역현대홈타운 | 8692 | 전체 |
| 서원마을3단지아이파크 | 8425 | 전체 |

거래 유형: **매매**만 추적 (전세·월세 제외)

## 2. 위험 사항 및 전제

### 2.1 네이버 부동산 데이터 수집의 약관 회색지대
- 네이버 부동산은 공식 API가 없으며 내부 API(`new.land.naver.com/api/articles/...`)를 호출하는 방식.
- 네이버 이용약관은 자동화 수집을 금지하나, **개인용 저빈도 비상업적 사용**은 사실상 묵인되는 영역.
- **상업적 사용·재배포·공유는 불가**.

### 2.2 IP 차단 가능성
- 빈번한 요청 시 IP 차단 가능. 보수적 호출 빈도 설계 필요.
- 단지당 일 약 8회 (daily 1회 + light-check 7회) — 단지가 2개면 일 16회.
- 요청 간 sleep, 적절한 User-Agent, 차단 시 백오프 적용.

### 2.3 API 구조 변경 위험
- 네이버 내부 API는 사전 공지 없이 바뀔 수 있음.
- 필수 필드 누락 감지 시 Telegram으로 즉시 알림 → 수동 점검.

## 3. 기능 요구사항

### 3.1 알림 종류

**A. Daily Summary (매일 08:30 KST)**
- 단지별 매물 수와 전일 대비 변동
- 평형별 최저가 / 평균가
- 신규 등록 매물 목록
- 가격 변동 매물 (임계치 이상)
- 최저가 TOP 3 매물 (단지별)

**B. Light Check (09~21시, 2시간 간격)**
- 신규 매물 등록 감지
- 가격 변동 감지 (임계치 ±3% 기본, 설정 가능)
- **변화가 없으면 메시지 미전송** (스팸 방지)

**C. 에러 알림 (필요 시)**
- 네이버 API 구조 변경 감지
- 연속 실패 누적 시

### 3.2 알림 메시지 형식
- Telegram HTML 파싱 모드 사용
- **하이퍼링크 적용 범위**: 각 매물 줄 + 단지명 + 하단 Google Sheets 링크 (옵션 C)
- 매물 링크: `https://new.land.naver.com/complexes/{단지ID}?articleNo={매물ID}`
- 단지 링크: `https://new.land.naver.com/complexes/{단지ID}`

### 3.3 설정 변경
- 단지 추가/제거: Google Sheets `settings` 탭에서 직접 편집 → 다음 실행부터 자동 반영
- 임계치(가격 변동 %), 알림 시간 등도 `settings` 탭에서 관리

## 4. 시스템 아키텍처

### 4.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (cron)                     │
│  ┌────────────────────────┐    ┌────────────────────────┐   │
│  │ daily-summary.yml      │    │ light-check.yml        │   │
│  │ 매일 08:30 KST         │    │ 09~21시 매 2시간       │   │
│  │ → run_daily.py 실행    │    │ → run_check.py 실행    │   │
│  └──────────┬─────────────┘    └──────────┬─────────────┘   │
└─────────────┼──────────────────────────────┼─────────────────┘
              ▼                              ▼
   ┌───────────────────────────────────────────────────┐
   │              파이썬 컴포넌트 (src/)                │
   │   naver_scraper → analyzer → telegram_notifier    │
   │           ↑                  ↑                    │
   │           └─── sheets_store ─┘                    │
   └─────────────────┬─────────────────────┬───────────┘
                     ▼                     ▼
              ┌──────────────┐      ┌──────────────┐
              │   Telegram   │      │ Google Sheets│
              └──────────────┘      └──────────────┘
```

### 4.2 기술 스택
| 영역 | 선택 |
|---|---|
| 언어 | Python 3.11+ |
| 실행 환경 | GitHub Actions (cron) |
| 데이터 저장 | Google Sheets (gspread) |
| 알림 | Telegram Bot API |
| HTTP 클라이언트 | httpx (재시도 내장) |
| 테스트 | pytest |
| 시크릿 관리 | GitHub Secrets |

## 5. 컴포넌트 책임

```
src/
├─ config.py              # 환경변수·시트 설정값 로딩
├─ naver_scraper.py       # 네이버 부동산 호출, 차단 대응
├─ sheets_store.py        # Google Sheets I/O
├─ analyzer.py            # 변화 감지, 요약 데이터 생성
├─ telegram_notifier.py   # 메시지 포맷팅 + 전송
├─ run_daily.py           # daily 진입점
└─ run_check.py           # light-check 진입점
.github/workflows/
├─ daily-summary.yml
└─ light-check.yml
tests/
├─ test_analyzer.py       # 가장 비중 높음
├─ test_scraper_parse.py
├─ test_notifier_format.py
└─ fixtures/              # 가짜 응답 JSON
```

### 5.1 컴포넌트 요약 표

| 컴포넌트 | 책임 | 외부 의존 | 예상 LoC |
|---|---|---|---|
| `config.py` | 환경변수·시트 설정 로딩, 단지 목록 제공 | - | ~50 |
| `naver_scraper.py` | 단지별 매물 리스트 가져오기, 재시도·차단 대응 | 네이버 내부 API | ~150 |
| `sheets_store.py` | 시트 5개 탭 읽기/쓰기 캡슐화 | Google Sheets API | ~120 |
| `analyzer.py` | 어제·오늘 비교, 변화 감지, 요약 통계 (순수 함수) | - | ~200 |
| `telegram_notifier.py` | HTML 메시지 포맷, 하이퍼링크, 전송 | Telegram Bot API | ~100 |
| `run_daily.py` | daily 흐름 오케스트레이션 | 위 5개 | ~50 |
| `run_check.py` | light-check 흐름 오케스트레이션 | 위 5개 | ~50 |
| **합계** | | | **~720** |

### 5.2 핵심 설계 결정

1. **`analyzer.py`는 순수 함수** — 외부 의존성 0. 두 매물 리스트(어제/오늘) 입력 → 변화 + 요약 출력. 단위 테스트가 매우 쉬움.
2. **`naver_scraper.py`가 네트워크 격리** — 차단·재시도·sleep 모두 이 파일 안. 다른 모듈은 "매물 리스트를 받는다"만 알면 됨.
3. **두 진입점 파일 분리** — `if mode == 'daily'` 분기 대신 별도 파일. 한쪽 워크플로우가 깨져도 다른 쪽 영향 없음.
4. **단방향 의존성** — `run_*` → `scraper/store/analyzer/notifier`. 거꾸로 흐르는 의존성 없음.

## 6. 데이터 모델

### 6.1 Google Sheets 탭 구조

| 탭 | 용도 | 갱신 빈도 |
|---|---|---|
| `settings` | 단지 목록, 임계치, 알림 시간 (사용자가 수정) | 사용자 필요 시 |
| `latest` | 가장 최근 매물 스냅샷 전체 | 매 실행 (덮어쓰기) |
| `history` | 일별 요약 (단지/평형별 최저가·평균가·매물수) | 매일 1줄/단지/평형 |
| `events` | 감지된 변화 이력 (신규 매물, 가격 변동 등) | 변화 발생 시 |
| `run_log` | 실행 성공/실패 기록 | 매 실행 |

### 6.2 `settings` 탭 스키마

**단지 목록 영역**
| 열 | 설명 | 예시 |
|---|---|---|
| A: 단지명 | 사람용 표시 이름 | 성복역현대홈타운 |
| B: 단지ID | 네이버 complex ID | 8692 |
| C: 관심평형 | 쉼표 구분 (빈칸 = 전체) | 84, 114 |
| D: 활성화 | TRUE/FALSE | TRUE |

**설정값 영역**
| 키 | 기본값 | 설명 |
|---|---|---|
| `price_change_threshold` | 3 | 가격 변동 알림 임계치(%) |
| `top_n_lowest` | 3 | 최저가 TOP N 매물 개수 |

### 6.3 `latest` 탭 스키마
```
단지ID | 매물ID | 평형 | 가격(만원) | 동 | 층 | 방향 | 등록일 | 매물URL | 스크랩시각
```

### 6.4 `history` 탭 스키마
```
날짜 | 단지ID | 평형 | 매물수 | 최저가 | 평균가 | 최고가
```
영구 보관 — 시트에서 직접 추세 그래프 작성 가능.

### 6.5 `events` 탭 스키마
```
시각 | 종류 | 단지ID | 매물ID | 상세 | 매물URL
```
종류 enum: `NEW_LISTING`, `PRICE_CHANGE`, `LISTING_REMOVED`

### 6.6 `run_log` 탭 스키마
```
시각 | 모드 | 결과 | 단지수 | 매물수 | 메시지
```
30일 이전 데이터는 앱이 자동 정리.

## 7. 실행 흐름

### 7.1 Flow A: Daily Summary (08:30 KST)

```
1. config.py: settings 시트 로드, 환경변수 로드
2. naver_scraper: 각 활성 단지의 매물 전체 수집
3. sheets_store: history 시트에서 D-1 요약 로드
4. analyzer:
   - 어제 vs 오늘 비교 → 변화 이벤트 추출
   - 평형별 최저가·평균가·매물수 집계
   - 최저가 TOP N 추출
5. sheets_store: latest 덮어쓰기 + history 1줄 추가 + events 추가
6. telegram_notifier: 풀 요약 메시지 작성 후 전송 (항상)
7. sheets_store: run_log 기록
```

### 7.2 Flow B: Light Check (09~21시, 2h)

```
1. config.py: settings 로드
2. naver_scraper: 매물 전체 수집
3. sheets_store: latest에서 직전 스냅샷 로드
4. analyzer: 직전 vs 지금 비교 → 신규/가격변동 추출
5. 변화 없음 → run_log만 기록하고 종료
   변화 있음 ↓
6. sheets_store: latest 갱신 + events 추가
7. telegram_notifier: 변동 알림 전송
8. sheets_store: run_log 기록
```

## 8. Telegram 메시지 포맷

### 8.1 Daily Summary 예시
```
🏠 HouseBOT 일일 요약 (2026-06-14 일)

━━━━━━━━━━━━━━━━━━
📍 성복역현대홈타운       ← 단지 페이지 링크
━━━━━━━━━━━━━━━━━━
📊 매물 수: 18건 (어제 17건, +1)

💰 평형별 시세
 • 84㎡  최저 12.5억 / 평균 13.2억 (3건)
 • 114㎡ 최저 14.8억 / 평균 15.5억 (5건)
 • 145㎡ 최저 18.0억 / 평균 19.2억 (10건)

🆕 신규 매물 (2건)
 • 114㎡, 14.8억, 102동 12층, 남향  ← 매물 링크
 • 145㎡, 18.0억, 105동 5층, 동향   ← 매물 링크

📉 가격 변동 (1건)
 • 84㎡: 13.0억 → 12.5억 (-3.8%)    ← 매물 링크

🏷 최저가 TOP 3
 1. 84㎡  12.5억 (101동 8층)         ← 매물 링크
 2. 114㎡ 14.8억 (102동 12층)        ← 매물 링크
 3. 145㎡ 18.0억 (105동 5층)         ← 매물 링크

━━━━━━━━━━━━━━━━━━
📊 전체 추이 보기 → Google Sheets   ← Sheets 링크
```

### 8.2 Light Check 예시 (변화 있을 때만)
```
🔔 변동 알림 (12:30)

📍 성복역현대홈타운
🆕 신규 매물 1건
 • 84㎡, 13.0억, 103동 15층, 남향

📉 가격 변동 1건 (임계치 ±3% 초과)
 • 145㎡: 19.5억 → 18.8억 (-3.6%)
```

### 8.3 에러 알림 예시
```
🚨 HouseBOT 에러

네이버 API 구조 변경 감지
단지: 성복역현대홈타운 (8692)
원인: 'dealPrice' 필드 누락

조치 필요: naver_scraper.py 점검
```

## 9. 에러 처리 & 안정성

| 시나리오 | 대응 |
|---|---|
| 네이버 일시 차단(403/429) | 지수 백오프 재시도 (1s → 3s → 10s). 실패 시 `run_log` 기록 후 다음 cron 회차에 재시도 |
| 네이버 API 구조 변경 | 필수 필드 누락 감지 → 즉시 Telegram 에러 알림 |
| Telegram 전송 실패 | 3회 재시도. 실패 시 GitHub Actions 로그에만 기록 |
| Google Sheets 일시 장애 | 5회 재시도 (gspread는 일시 503 가끔 발생) |
| 단지 1개 실패 | 다른 단지는 계속 처리 (부분 실패 허용) |
| 하루 동안 한 번도 성공 못함 | 다음날 daily 실행 시 "어제 데이터 없음" 감지 → Telegram 알림 |
| 시크릿 관리 | 봇 토큰·Chat ID·Sheets ID·Google 서비스 계정 키 모두 GitHub Secrets |

원칙: **부분 실패 허용 + 자동 복구 + 진짜 위험한 변화만 알림**.

## 10. 테스트 전략

| 컴포넌트 | 테스트 방식 |
|---|---|
| `analyzer.py` ⭐ | 단위 테스트 집중. 가짜 매물 리스트로 변화 감지·집계 결과 검증 |
| `naver_scraper.py` | 가짜 HTTP 응답(JSON fixture) 모킹 후 파싱 결과 검증 |
| `sheets_store.py` | gspread 모킹. 시트 I/O 입출력 검증 |
| `telegram_notifier.py` | 메시지 포맷팅 결과 문자열 검증 (전송 X) |
| 전체 흐름 | `DRY_RUN=true` 모드 — 실제 네이버 호출하되 Telegram·Sheets 쓰기는 콘솔 출력만 |

첫 배포 전 **DRY_RUN 1회 + 실제 1회** 검증.

## 11. 시크릿 관리

GitHub Secrets에 저장할 항목:
| 키 이름 | 내용 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 발급 토큰 |
| `TELEGRAM_CHAT_ID` | 사용자 Chat ID |
| `GOOGLE_SHEETS_ID` | Google Sheets 문서 ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 키 JSON (전체) |

로컬 개발: `.env` 파일 (`.gitignore`에 포함, 절대 커밋 X).

## 12. 데이터 보관 정책

| 탭 | 보관 정책 | 1년 후 예상 크기 |
|---|---|---|
| `settings` | 영구 (사용자 관리) | ~10줄 |
| `latest` | 매번 덮어쓰기 | ~50줄 |
| `history` | 영구 보관 | 단지 2개·평형 3개 × 365일 ≈ 2,200줄 |
| `events` | 영구 보관 | 추정 수백~수천줄 |
| `run_log` | 최근 30일 | ~250줄 |

Google Sheets 한계(셀 1천만 개)와 비교해 충분히 여유.

## 13. 향후 확장 (현 범위 밖)

- 거래 유형 확장 (전세·월세 추가)
- 단지별 알림 채널 분리 (지금은 단일 Chat ID)
- 가격 추세 그래프 이미지 첨부
- 이상치 자동 강조 (평균 대비 큰 폭 하락 매물)
- Slack/카카오톡 추가 채널

(처음부터 구현하지 않고, 운영하면서 필요한 것만 점진적 추가)
