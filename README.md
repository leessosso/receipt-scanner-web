# receipt-scanner-web

스마트폰에 모아 둔 영수증 사진을 올리면서 **일자·금액·메모를 바로 입력**하면,
사진은 구글 드라이브에, 내용은 구글 시트에 한 행으로 쌓이는 풀스택 웹
서비스입니다. 시트에는 미리보기(`IMAGE`)와 원본 링크가 함께 들어가 사진과 내용을
같이 볼 수 있습니다.

## 아키텍처

모노레포 구조입니다.

```
.
├── backend/    # FastAPI (저장 API + 기존 원근 보정)
└── frontend/   # Next.js (App Router) + Tailwind CSS (모바일 입력 UI)
```

- **Backend**: `POST /api/receipts` 로 이미지와 일자/금액/메모를 받아 지정한
  드라이브 폴더에 파일을 올리고, 스프레드시트에 행을 추가합니다.
  (`POST /api/receipt/transform` 원근 보정·OCR은 남아 있으나 기본 UI에서는
  사용하지 않습니다.)
- **Frontend**: 카메라/갤러리 업로드, 사진 미리보기, 일자·금액·메모 입력,
  시트 저장, 다음 장 연속 입력.

시트 컬럼 (기본 `A:F`):

| A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- |
| 일자 | 금액 | 메모 | 사진 미리보기 | 원본 링크 | 등록시각 |

1행에 위 헤더를 미리 적어 두면 이후 행이 그 아래로 이어집니다.

## 사전 요구사항

- Python 3.10+ (개발/검증은 3.12 기준, `python3-venv` 필요)
- Node.js 18+ (검증은 v22 기준)
- Google Cloud 프로젝트와 **서비스 계정** (Drive·Sheets API 사용)

## 구글 시트/드라이브 연결

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트를
   만들고 **Google Drive API**, **Google Sheets API** 를 사용 설정합니다.
2. 서비스 계정을 만들고 JSON 키를 다운로드합니다.
3. 영수증을 모을 **드라이브 폴더**와 **스프레드시트**를 만든 뒤, 둘 다 서비스
   계정 이메일(`...@....iam.gserviceaccount.com`)에 편집 권한으로 공유합니다.
4. 스프레드시트 URL의 `/d/` 다음 ID가 `GOOGLE_SPREADSHEET_ID`, 드라이브 폴더
   URL의 폴더 ID가 `GOOGLE_DRIVE_FOLDER_ID` 입니다.
5. `backend/.env.example` 을 참고해 백엔드 환경변수를 설정합니다.

```bash
# 키 파일 경로를 쓰는 경우
export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
export GOOGLE_SPREADSHEET_ID=your-spreadsheet-id
export GOOGLE_DRIVE_FOLDER_ID=your-folder-id
# 시트 탭 이름이 Sheet1이 아니면 예: '시트1!A:F'
# export GOOGLE_SHEET_RANGE=A:F
```

업로드된 사진은 시트 `IMAGE()` 미리보기를 위해 **링크가 있는 모든 사용자**가
볼 수 있게 공유됩니다. 원본은 드라이브 폴더에도 남습니다.

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
  기본값은 `http://localhost:3000,http://127.0.0.1:3000` (및 3001) 입니다.

### 2) 프론트엔드 (Next.js)

```bash
cd frontend
npm install
npm run dev
```

- 앱: <http://localhost:3000>
- 백엔드 주소는 `NEXT_PUBLIC_API_BASE_URL` 로 재정의할 수 있습니다
  (기본값 `http://localhost:8000`). `frontend/.env.example` 참고.

## 테스트

```bash
# 백엔드 (pytest: 저장 API mock / 변환 파이프라인)
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
