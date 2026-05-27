# Now What

AI 기반 일정 관리와 목표 계획 생성을 실험하는 풀스택 프로젝트입니다. 프론트엔드는 Next.js, 백엔드는 FastAPI, 데이터베이스는 PostgreSQL을 사용합니다.

## 프로젝트 구성

- `app/`: Next.js App Router 화면
- `components/`, `lib/`: 프론트엔드 공통 컴포넌트와 API 클라이언트
- `backend/`: FastAPI API, 서비스 로직, SQLAlchemy 모델
- `alembic/`: PostgreSQL 마이그레이션
- `scripts/`: 샘플 데이터 생성과 API 스모크 테스트
- `docs/`: API 목록과 생성된 API 레퍼런스

## 처음 받은 사람이 먼저 할 일

아래 명령은 Windows PowerShell 기준입니다.

### 1. 필수 프로그램 확인

- Node.js `20.9.0` 이상
- Python `3.12` 이상
- Docker Desktop
- PowerShell

버전 확인:

```powershell
node -v
npm -v
py --version
docker --version
```

### 2. 프로젝트 폴더로 이동

GitHub에서 clone 받은 저장소 루트로 이동합니다.

```powershell
git clone <repository-url>
cd now-what
```

이 폴더에는 `package.json`, `requirements.txt`, `docker-compose.yml`, `backend/`, `app/`이 있어야 합니다.

### 3. 환경 변수 파일 만들기

```powershell
Copy-Item .env.example .env
```

로컬 실행은 기본값으로 대부분 동작합니다. 다만 아래 값은 상황에 맞게 확인하세요.

- `DATABASE_URL`: 기본값은 Docker PostgreSQL(`planner:planner@localhost:5432/ai_planner`)입니다.
- `JWT_SECRET_KEY`: 로컬에서는 예시값으로도 실행되지만, 공유/배포 환경에서는 긴 랜덤 문자열로 바꾸세요.
- `GEMINI_API_KEY`: 없으면 목표 계획 생성이 템플릿 fallback으로 동작합니다.
- `GOOGLE_CLIENT_ID`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID`: 일반 Next.js 화면의 Google 로그인에 필요합니다. 백엔드 데모 페이지의 이메일/비밀번호 로그인만 쓸 때는 없어도 됩니다.
- `ALLOWED_ORIGINS`: 프론트엔드 포트를 바꾸면 해당 주소를 추가하세요.

### 4. 백엔드 준비

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
docker compose up -d
.\.venv\Scripts\alembic.exe upgrade head
```

백엔드 실행:

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

확인 주소:

- API 문서: http://127.0.0.1:8000/docs
- 헬스 체크: http://127.0.0.1:8000/api/v1/health
- DB 헬스 체크: http://127.0.0.1:8000/api/v1/health/db

### 5. 프론트엔드 준비

새 터미널을 프로젝트 루트에서 열고 실행합니다.

```powershell
npm ci
npm run dev
```

확인 주소:

- 프론트엔드: http://localhost:3000

프론트엔드 API 기본 주소는 현재 브라우저 호스트의 `:8000`입니다. 백엔드 주소를 따로 써야 하면 `.env`에 다음 값을 추가하세요.

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## 일반 화면 사용법

일반 Next.js 화면은 좌측 사이드바에서 이동합니다.

- `/`: 대시보드 요약 화면
- `/manage`: 고정 일정과 가변 작업 등록/조회/삭제
- `/schedule`: 월간 캘린더
- `/schedule/week`: 주간 시간표. 월간 캘린더에서 주를 클릭하면 이동합니다.
- `/settings`: 시간 표시 범위, 시간 형식, 다크 모드 설정

주의: 일반 프론트엔드 로그인은 현재 Google OAuth 버튼 기준입니다. `NEXT_PUBLIC_GOOGLE_CLIENT_ID`가 없으면 사이드바에 `Google setup required`가 표시됩니다. Google 설정 없이 API 전체 흐름을 먼저 확인하려면 아래 `User Flow Demo`를 사용하세요.

## User Flow Demo 사용법

백엔드 서버가 실행 중일 때 아래 주소를 엽니다.

- http://127.0.0.1:8000/api/v1/demo/user-flow

이 페이지는 프론트엔드 로그인 설정 없이도 이메일/비밀번호 계정을 만들고, 보호 API에 `Authorization: Bearer <token>`을 자동으로 붙여 전체 사용자 흐름을 검증하는 데모입니다.

### 빠른 실행

1. 상단의 `샘플 흐름 끝까지 실행`을 누릅니다.
2. 오른쪽 `실행 상태`에서 `User ID`, `Schedule ID`, `Task ID`, `Goal ID`가 채워지는지 확인합니다.
3. `마지막 요청`과 `마지막 응답`에서 실제 API payload와 응답 JSON을 확인합니다.
4. 하단 `Calendar` 영역에 고정 일정, 가변 작업 배정, AI 계획 항목이 같이 나타나는지 확인합니다.

### 단계별 실행

1. `가입/로그인`
   - 기본 이메일은 `user-flow-{timestamp}@example.com`이며 실행 시 고유 이메일로 바뀝니다.
   - `가입 후 로그인`을 누르면 계정 생성 후 토큰이 저장됩니다.
   - 이미 만든 계정이면 이메일/비밀번호를 입력하고 `로그인`을 누릅니다.
   - 문제가 생기면 `토큰 지우기`나 상단 `상태 초기화`를 사용합니다.

2. `일정 세팅`
   - `고정 일정 등록`: 회의, 수업, 운동처럼 자동 배정이 피해야 하는 시간을 만듭니다.
   - `반복 유형`을 `반복 일정`으로 바꾸면 `daily`, `weekly`, `biweekly` 반복을 테스트할 수 있습니다.
   - `가변 작업 등록`: 마감, 총 예상 시간, 최소/선호 세션 길이, 하루 최대 시간, 우선순위를 입력합니다.
   - 각 카드의 상세 조회, 수정, 삭제 버튼으로 CRUD 동작을 바로 확인할 수 있습니다.

3. `목표 분석과 계획 생성`
   - `자연어 목표`에 원하는 목표를 입력합니다.
   - `목표 분석하기`를 누르면 `/api/v1/goals/intake`가 호출되고, AI가 이해한 목표와 추가 질문이 생성됩니다.
   - 질문 카드에 답변을 채우면 `answers_json preview`가 즉시 갱신됩니다.
   - `목표 저장 + 계획 생성`을 누르면 `/api/v1/goals/complete`가 호출되어 목표와 plan item이 저장됩니다.

4. `자동 배치와 캘린더`
   - `배치 + 캘린더 조회`는 `/api/v1/planner/allocate` 후 `/api/v1/calendar`를 호출합니다.
   - 기본 배정 정책은 `.env`의 `DEFAULT_DAY_START`, `DEFAULT_DAY_END`, `DEFAULT_BUFFER_MINUTES`, `DEFAULT_MAX_AUTO_MINUTES_PER_DAY` 값을 사용합니다.
   - `캘린더 조회`는 기존 데이터를 다시 불러오고, `배치 후 조회`는 현재 범위로 다시 allocate한 뒤 결과를 보여줍니다.

5. `목표/계획/캘린더 관리`
   - `내 목표 목록`에서 로그인한 사용자의 목표를 불러오고 선택/삭제할 수 있습니다.
   - `생성된 계획`에서는 plan 요약과 plan item을 확인합니다.
   - plan item은 일정 비우기, 건너뛰기, 삭제 액션을 테스트할 수 있습니다.
   - 캘린더 이벤트에서도 고정 일정 삭제, 배정 삭제, 가변 작업 삭제, plan item 상태 변경을 바로 실행할 수 있습니다.

보조 데모 페이지:

- API Playground: http://127.0.0.1:8000/api/v1/demo/goal-intake
- Calendar Demo: http://127.0.0.1:8000/api/v1/demo/calendar

## 샘플 데이터 넣기

프론트엔드와 API 화면에서 볼 샘플 데이터를 만들려면 백엔드 의존성 설치와 DB 마이그레이션 후 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\seed_frontend_sample_data.py
```

스크립트는 `frontend-sample@example.com` 계정, 고정 일정, 가변 작업, 목표, AI plan item, 7일 배정 결과를 생성합니다. 출력에 표시되는 `sample_password`로 API Playground나 User Flow Demo에서 로그인할 수 있습니다.

## 테스트와 점검

백엔드 서버를 실행한 상태에서 전체 API 스모크 플로우를 확인합니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_api_flow.py
```

프론트엔드 정적 검사:

```powershell
npm run lint
```

백엔드 테스트:

```powershell
.\.venv\Scripts\pytest.exe
```

프로덕션 빌드:

```powershell
npm run build
```

`npm run build`는 `next/font`를 통해 Google Fonts를 가져올 수 있어 네트워크 접근이 필요할 수 있습니다.

## 주요 API 흐름

인증이 필요 없는 엔드포인트:

- `GET /api/v1/health`
- `GET /api/v1/health/db`
- `POST /api/v1/users`
- `POST /api/v1/users/register`
- `POST /api/v1/users/login`

로그인 후 `Authorization: Bearer <access_token>`이 필요한 대표 엔드포인트:

- `GET /api/v1/auth/me`
- `GET /api/v1/users`
- `POST /api/v1/schedules/fixed`
- `GET /api/v1/schedules/fixed`
- `POST /api/v1/tasks/flexible`
- `GET /api/v1/tasks/flexible`
- `POST /api/v1/goals/intake`
- `POST /api/v1/goals/complete`
- `POST /api/v1/planner/allocate`
- `GET /api/v1/calendar`

전체 API 목록은 `docs/backend-api-list.md`, 생성된 API 레퍼런스는 `docs/api-reference.md`를 참고하세요.

## 자주 막히는 지점

- `GET /api/v1/health/db`가 실패하면 Docker Desktop과 `docker compose up -d` 상태를 확인하세요.
- `alembic` 명령을 찾지 못하면 가상환경 경로를 포함해 `.\.venv\Scripts\alembic.exe upgrade head`로 실행하세요.
- 브라우저에서 API 호출이 CORS 오류로 막히면 `.env`의 `ALLOWED_ORIGINS`에 프론트엔드 주소를 추가하세요.
- 일반 프론트엔드에서 로그인이 안 되면 Google OAuth 환경 변수를 먼저 설정하거나, `User Flow Demo`로 이메일/비밀번호 기반 API 흐름을 검증하세요.
- 목표 계획 생성이 Gemini 응답 없이 진행되면 `GEMINI_API_KEY`가 없거나 잘못된 상태일 수 있습니다. 이 경우 템플릿 fallback 결과가 반환될 수 있습니다.
