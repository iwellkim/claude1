# 📊 비즈니스 데이터 분석 플랫폼

업로드한 비즈니스 데이터(CSV · Excel · JSON · Parquet 등)를 자동으로 프로파일링해
**할 수 있는 분석을 추천** 하고, 선택 또는 자연어 요청을 받아 **비주얼 HTML 보고서** 를
만들어 주는 Flask 기반 웹 앱입니다.

## 📱 휴대폰에서 바로 실행 — GitHub Codespaces (설치 0, 클릭 3번)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/iwellkim/claude1/tree/claude/data-analysis-platform-AHVHw)

1. 위 버튼 → GitHub 계정으로 로그인 → **"Create codespace"** 누르면 자동으로
   - Python · 한글 폰트(NanumGothic, Noto CJK) 설치
   - 의존성 설치
   - Flask 서버(포트 5000) 자동 기동
2. 우측 하단 **"PORTS"** 탭 → 5000 포트 옆 🌐 아이콘 → 브라우저에서 열림
3. 그 URL 을 휴대폰 브라우저에 복붙하거나, 휴대폰에서 github.com 에 로그인해 Codespace 열면
   모바일 브라우저에서도 동일하게 동작합니다.

> 💡 무료 할당량: 개인 계정 월 120 시간. 사용 안 할 땐 Codespace 를
> **Stop** 하면 시간이 소진되지 않습니다.

- 🔎 자동 컬럼 프로파일링: 역할(수치/범주/시간/ID) 추정, 결측·중복·분포 요약
- 💡 분석 추천: 개요, 분포, 상관, 시계열, 세그먼트 비교, 교차표, 이상치,
  TOP/BOTTOM, 세그먼트별 시계열, K-평균 군집화
- 🗣 **자연어 사용자 요청** 도 지원 (예: "지역별 매출 시계열 추세", "k=3 군집화")
- 📝 **비주얼 웹 보고서** 자동 생성 (핵심 요약 + KPI 카드 + 차트 + 표 + 인사이트)
- 🇰🇷 **한글 폰트 안전**: 시스템 한글 폰트를 자동 탐지하고, 없으면
  `assets/fonts/` 에 번들된 폰트를 등록해 차트 글자가 깨지지 않습니다.

## 빠른 시작

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/make_sample_data.py        # (선택) 샘플 CSV 생성
python run.py                              # http://localhost:5000
```

브라우저에서 열고 → 파일 업로드 → 추천 분석 체크 또는 자연어 요청 입력 →
**"선택한 분석 실행"** 클릭 → 새 탭에서 HTML 보고서가 열립니다.

## 한글 폰트 가이드

차트의 한글이 네모로 표시되면 아래 중 하나를 하세요.

1. 시스템에 한글 폰트 설치
   - macOS: 기본 설치되어 있습니다 (AppleGothic).
   - Windows: 기본 설치되어 있습니다 (Malgun Gothic).
   - Ubuntu/Debian: `sudo apt-get install -y fonts-nanum fonts-noto-cjk`
2. 또는 `.ttf` / `.otf` 파일을 `assets/fonts/` 디렉토리에 넣으세요.
   서버 시작 시 자동으로 matplotlib 에 등록합니다.

웹 UI 우상단과 보고서 푸터에 현재 사용 중인 폰트 이름이 표시됩니다.

## 지원 분석 (키)

| key | 설명 |
| --- | --- |
| `overview` | 전반적 개요, 결측·중복, 기술통계 (항상 포함) |
| `distribution` | 히스토그램 · 박스플롯 · 왜도/첨도 |
| `correlation` | 피어슨 상관 히트맵 + 강한 상관 쌍 |
| `time_series` | 시계열 추세 (자동 리샘플 + 이동평균) |
| `segment` | 그룹별 합계/평균/분포 비교 |
| `crosstab` | 두 범주 간 교차표 · 카이제곱 |
| `outliers` | IQR · Z-score 이상치 탐지 |
| `top_bottom` | 매출 기준 상/하위 항목 |
| `trend_by_segment` | 세그먼트별 시계열 추세 |
| `kmeans` | K-평균 군집화 (자동 표준화) |

## 자연어 요청 예시

- "월별 매출 추세 보여줘"
- "지역별 매출 비교"
- "가격과 수량 상관관계"
- "이상치 찾아줘"
- "카테고리와 채널 교차표"
- "k=3 군집화"

여러 요청을 **세미콜론(;)** 으로 구분해 한 번에 제출할 수 있습니다.

## 프로젝트 구조

```
app/
  fonts.py           # 한글 폰트 자동 설정
  data_loader.py     # 파일→DataFrame (인코딩 자동 감지)
  profiler.py        # 컬럼 프로파일 + 분석 추천
  analyses.py        # 각 분석 실행기 (차트/표/KPI/인사이트)
  custom_request.py  # 자연어 요청 파서
  report.py          # HTML 보고서 렌더링
  charts.py          # matplotlib → base64 PNG
  server.py          # Flask 엔드포인트
templates/
  index.html         # 업로드 + 추천 UI
  report.html        # 결과 보고서 템플릿
scripts/
  make_sample_data.py
```

## API (요약)

- `POST /api/upload` (multipart: `file`) → `{session_id, summary, profiles, recommendations}`
- `POST /api/analyze` (JSON: `{session_id, selected:[idx], custom:"..."}`) → `{report_url}`
- `GET  /reports/<name>` → 생성된 HTML 보고서 반환

## 라이선스

내부 사용 목적의 예시 구현입니다.
