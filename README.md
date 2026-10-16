# 일어나

> 내 기록을 이해하는 다정한 AI 운동 비서

일어나는 삼성 헬스의 `일일 활동` 화면에서 걸음 수, 활동 시간, 활동 칼로리, 이동 거리를 읽고, 날짜별 운동 기록과 체중 변화를 바탕으로 부담 없는 다음 행동을 제안하는 성인용 웹 서비스입니다.

의료·건강 진단 서비스가 아닙니다. 질병, 약물, 치료, 극단적인 감량법은 다루지 않습니다.

## 주요 기능

- Google 로그인과 사용자별 데이터 분리
- 삼성 헬스 일일 활동 스크린샷 AI 추출 및 저장 전 확인
- 활동·체중 데이터 CRUD와 통계 요약
- 기록 요약을 시스템 지침에 주입한 AI 운동 채팅
- 사용자당 하나의 연속 대화 자동 저장·복원·초기화
- 최근 흐름을 반영한 100보 단위 주간 걸음 목표 제안
- 주간·월간 걸음 수와 체중 그래프
- CSV 내보내기와 라이트·다크 모드
- 7일 간격의 부드러운 체중 체크인 알림

## 기술 스택

- Backend: Python 3.10+, FastAPI, Pydantic v2, Firebase Admin SDK
- Database/Auth: Firebase Authentication, Cloud Firestore
- AI: OpenAI Responses API의 이미지 입력 및 Structured Outputs
- Frontend: Vanilla HTML, CSS, JavaScript, Chart.js
- Deploy: Render(백엔드), Vercel(프론트엔드)

## 프로젝트 구조

```text
backend/
  app/
    routers/       # profile, data, conversation, AI, account API
    services/      # summary, OpenAI, rate limiting
    config.py      # 환경 변수
    dependencies.py# Firebase 인증
    schemas.py     # Pydantic 계약
    store.py       # Firestore / 테스트용 메모리 저장소
  tests/
frontend/
  api/config.js    # Vercel 공개 런타임 설정
  public/          # 모바일 웹 UI
scripts/
  import_samsung_health.py
docs/product-requirements.md
plans/ileona-mvp.md
```

## 로컬 실행

### 1. 백엔드

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

기본 `.env.example`은 인메모리 DB와 개발용 `X-Debug-User` 인증을 사용합니다. 브라우저에서는 로컬 데모 버튼이 같은 사용자를 사용합니다.

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 2. 프론트엔드

`frontend/public`을 VS Code Live Server 등 정적 서버로 엽니다. `/api/config`가 없는 로컬 정적 서버에서는 자동으로 `http://localhost:8000`과 개발 인증을 사용합니다.

Node.js가 있다면:

```bash
cd frontend
npx serve public -l 5500
```

### 3. 테스트

```bash
cd backend
pytest -q
```

## 삼성 헬스 기존 기록 가져오기

내보내기 ZIP은 저장소나 서버에 올리지 않습니다. 로컬 도구가 `activity.day_summary` CSV만 읽어 날짜별 기록을 미리 보여주고, `--apply`를 지정했을 때 정규화한 값만 API로 보냅니다.

미리보기:

```bash
python scripts/import_samsung_health.py "C:\path\to\samsunghealth_export.zip"
```

로컬 개발 DB에 저장:

```bash
python scripts/import_samsung_health.py "C:\path\to\samsunghealth_export.zip" --apply --debug-user demo-user
```

프로덕션에는 Firebase ID 토큰을 `--token`으로 전달합니다. 원본 ZIP, ECG, 심박수, 수면, 위치 등 다른 건강 데이터는 읽거나 전송하지 않습니다.

## 환경 변수

### Render / FastAPI

| 변수 | 설명 |
|---|---|
| `APP_ENV` | 프로덕션에서는 `production` |
| `AUTH_MODE` | 프로덕션에서는 `firebase` |
| `USE_IN_MEMORY_DB` | 프로덕션에서는 `false` |
| `ALLOWED_ORIGINS` | 쉼표로 구분한 Vercel 주소 |
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 전체 문자열 |
| `OPENAI_API_KEY` | 서버 전용 OpenAI API 키 |
| `OPENAI_MODEL` | 텍스트와 이미지 입력을 지원하는 모델 |
| `OPENAI_MAX_OUTPUT_TOKENS` | 응답 출력 제한, 기본 500 |
| `MAX_IMAGE_BYTES` | 이미지 최대 바이트, 기본 5MB |

### Vercel / 공개 웹 설정

| 변수 | 설명 |
|---|---|
| `API_BASE_URL` | Render API 주소 |
| `AUTH_MODE` | `firebase` |
| `FIREBASE_WEB_API_KEY` | Firebase 웹 API 키(공개 설정) |
| `FIREBASE_AUTH_DOMAIN` | Firebase Auth 도메인 |
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID |
| `FIREBASE_APP_ID` | Firebase 웹 앱 ID |

Firebase 웹 설정은 브라우저용 공개 식별자입니다. 서비스 계정 JSON과 OpenAI 키는 절대 Vercel 프론트엔드 변수나 코드에 넣지 않습니다.

## Firebase 설정

1. Firebase Authentication에서 Google 제공업체를 활성화합니다.
2. Vercel 도메인을 Authentication의 승인된 도메인에 추가합니다.
3. Firestore Database를 생성합니다.
4. `firestore.rules`를 배포해 브라우저의 직접 접근을 막습니다.
5. 서비스 계정 JSON을 한 줄 JSON 문자열로 Render 환경 변수에 등록합니다.

Firestore 컬렉션:

```text
profiles/{uid}
data/{deterministicRecordId}
conversations/{uid}
conversations/{uid}/messages/{messageId}
```

대화는 사용자당 하나지만 메시지를 하위 문서로 나누어 Firestore 단일 문서 크기 제한과 쓰기 충돌을 피합니다.

## 배포

### Render

저장소 루트의 `render.yaml`을 사용하거나 다음 값을 직접 설정합니다.

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check: `/health`

무료 티어는 첫 요청이 느릴 수 있으므로 UI에서 로딩 상태를 유지하고 재시도 가능한 오류를 표시합니다.

### Vercel

- Root Directory: `frontend`
- Output Directory: `public`
- 위 Vercel 환경 변수를 설정합니다.

`/api/config` 서버리스 함수는 브라우저에 공개 가능한 설정만 반환합니다.

## API 요약

모든 `/api/*` 요청은 Firebase Bearer 토큰이 필요합니다. 개발 모드에서만 `X-Debug-User`를 사용할 수 있습니다.

| Method | Path | 기능 |
|---|---|---|
| PUT/GET | `/api/profile` | 프로필 저장·조회 |
| POST/GET | `/api/data` | 시계열 기록 추가·목록 |
| PUT/DELETE | `/api/data/{id}` | 기록 수정·삭제 |
| GET | `/api/data/summary` | 활동·체중 요약 |
| POST | `/api/data/import/screenshot` | 일일 활동 화면 추출 |
| GET | `/api/data/export.csv` | 내 기록 내보내기 |
| POST | `/api/chat` | 요약 기반 운동 채팅과 자동 저장 |
| POST/GET | `/api/conversations` | 단일 대화 추가·목록 |
| GET/DELETE | `/api/conversations/primary` | 대화 불러오기·초기화 |
| POST | `/api/profile/step-goal/recommend` | 주간 목표 제안 |
| POST | `/api/profile/step-goal/accept` | 제안 수락 |
| DELETE | `/api/account` | 내 앱 데이터와 Firebase 사용자 삭제 |

중복 날짜의 같은 기록 유형은 `409`를 반환합니다. 사용자가 덮어쓰기를 확인하면 `POST /api/data?overwrite=true`를 호출합니다.

## 보안·개인정보 원칙

- 업로드 이미지는 메모리에서 검증·재인코딩해 EXIF를 제거한 뒤 처리하고 저장하지 않습니다.
- 이미지 안의 텍스트는 지시가 아닌 데이터로 취급합니다.
- OpenAI 요청은 `store=false`로 전송합니다.
- 이메일과 이름은 운동 프롬프트에 포함하지 않습니다.
- AI 호출은 사용자별 시간당 제한을 적용합니다.
- 실제 ZIP, 스크린샷, CSV, 키 파일은 `.gitignore`로 제외합니다.
- 계정 삭제 전 CSV 내보내기를 사용할 수 있습니다.

## 제출 전 체크리스트

- [ ] Vercel 프론트 URL
- [ ] Render API URL
- [ ] Render `/docs` URL
- [ ] 100개 이상 실제 일일 활동 데이터 확인
- [ ] 데이터 요약과 질문·답변이 함께 보이는 채팅 화면 캡처
- [ ] 스크린샷 추출값 확인 또는 기록 삭제가 보이는 CRUD 화면 캡처
- [ ] `현재 대화`를 선택해 메시지가 다시 표시되는 화면 캡처
- [ ] 환경 변수에 비밀값이 있고 Git 기록에는 없는지 확인
- [ ] 모바일 390×844와 데스크톱 1440×900 렌더링 확인

## 배포 URL

- Frontend: 배포 후 입력
- Backend API: 배포 후 입력
- Swagger UI: 배포 후 입력
