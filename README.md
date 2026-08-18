# receipt-scanner-web

스마트폰으로 비스듬하게 촬영한 영수증 사진을 업로드하면, 백엔드에서 **원근 왜곡을
보정(perspective correction)** 하여 똑바른 직사각형 이미지로 변환해 주는 풀스택 웹
서비스입니다. 추후 OCR(텍스트 추출) 단계를 손쉽게 붙일 수 있도록 이미지 처리
파이프라인이 작은 유틸리티 단위로 분리되어 있습니다.

## 아키텍처

모노레포 구조입니다.

```
.
├── backend/    # FastAPI + OpenCV (원근 보정 API)
└── frontend/   # Next.js (App Router) + Tailwind CSS + Lucide (모바일 UI)
```

- **Backend**: `POST /api/receipt/transform` 로 이미지를 받아
  Grayscale → Gaussian Blur → Canny → Contour 탐색 → `approxPolyDP` 로 4각형 검출 →
  `getPerspectiveTransform`/`warpPerspective` 로 평면화 → 대비/샤프닝 보정을 수행합니다.
  4각형 검출에 실패하면 대비 보정만 적용한 원본을 반환합니다(fallback).
  `?response_format=json&ocr=true` 를 붙이면 보정 이미지와 함께 **Tesseract OCR** 로
  추출한 텍스트 및 구조화 필드(가맹점/날짜/소계/세금/합계/항목)를 반환합니다.
- **Frontend**: 카메라 촬영/갤러리 업로드, 미리보기, 보정 요청(로딩 스피너),
  원본 vs 보정 비교 뷰, 90도 회전 및 JPEG 다운로드, OCR 토글 및 추출 결과 표시
  기능을 제공합니다.

## 사전 요구사항

- Python 3.10+ (개발/검증은 3.12 기준, `python3-venv` 필요)
- Node.js 18+ (검증은 v22 기준)
- Tesseract OCR 엔진 (`tesseract-ocr`, OCR 기능 사용 시)

## 로컬 실행 방법

### 1) 백엔드 (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- 헬스 체크: <http://localhost:8000/api/health>
- API 문서(Swagger): <http://localhost:8000/docs>
- CORS 허용 오리진은 환경변수 `CORS_ORIGINS`(콤마 구분)로 재정의할 수 있으며,
  기본값은 `http://localhost:3000,http://127.0.0.1:3000` 입니다.

### 2) 프론트엔드 (Next.js)

```bash
cd frontend
npm install
npm run dev
```

- 앱: <http://localhost:3000>
- 백엔드 주소는 `NEXT_PUBLIC_API_BASE_URL` 로 재정의할 수 있습니다
  (기본값 `http://localhost:8000`). `frontend/.env.example` 참고.

### 3) 빠른 테스트

기울어진 샘플 영수증 이미지를 생성해 API로 직접 확인할 수 있습니다.

```bash
cd backend
source .venv/bin/activate
python scripts/make_sample.py          # samples/skewed_receipt.jpg 생성
curl -F "file=@samples/skewed_receipt.jpg" \
  "http://localhost:8000/api/receipt/transform" --output transformed.jpg
```

`response_format=json` 쿼리를 붙이면 Base64 이미지와 검출 메타데이터가 담긴 JSON을
받을 수 있고, 여기에 `&ocr=true` 를 더하면 추출 텍스트와 구조화 필드가 포함됩니다.

## 테스트

```bash
# 백엔드 (pytest: 변환 파이프라인 / OCR 파싱 / API 엔드포인트)
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest

# 프론트엔드 (vitest: 순수 유틸)
cd frontend
npm test
```

## Cloud Agent 환경

`.cursor/environment.json` 이 설치(`scripts/setup.sh`)와 두 개의 상시 터미널
(`backend`, `frontend`)을 정의합니다. 새 Cloud Agent가 시작되면 백엔드(8000)와
프론트엔드(3000)가 자동으로 기동됩니다.

## OCR 구조 및 확장

OCR 단계는 검출/보정 코어와 분리되어 있습니다.

- `backend/app/image_processing.py` 의 `transform_receipt()` 가 평면화된
  `np.ndarray` 를 반환합니다.
- `backend/app/ocr.py` 의 `extract_receipt()` 가 이 이미지를 이진화한 뒤
  Tesseract 로 텍스트를 읽고, `parse_receipt()` 가 필드로 파싱합니다.

**한국어 지원**: 기본 OCR 언어는 `kor+eng` 로, 한국어/영어 영수증을 모두 처리합니다.
두 컬럼(좌측 품목 · 우측 금액) 영수증에서 Tesseract가 열을 분리해 읽는 문제를
`image_to_data` 의 단어 좌표로 **행을 재구성**해 해결하고, `₩/원` 또는 한글 존재
여부로 통화(KRW/USD)를 감지하며, `6,300` 같은 정수(원) 금액과 전화·사업자번호
오인식을 구분합니다.

확장 예: 다른 언어는 `lang` 파라미터로 코드를 넘기고 해당 `tesseract-ocr-<lang>`
패키지를 설치하면 되고, 파싱 규칙은 `parse_receipt()` 의 정규식/휴리스틱을 조정합니다.
