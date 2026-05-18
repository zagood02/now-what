# AI Planner - Full Stack Application

시간표 제작 및 스케줄 수행 보조 프로그램입니다. Next.js 프론트엔드와 FastAPI 백엔드를 함께 사용해 고정 일정, 가변 작업, 목표 분석, 계획 생성, 자동 배정, 캘린더 조회 흐름을 제공합니다.

This project combines a Next.js frontend and a FastAPI backend to manage fixed schedules, flexible tasks, goal intake, plan generation, automatic allocation, and calendar views.

## Overview / 개요

### Frontend / 프론트엔드

- Next.js 기반 일정 관리 UI
- 고정 일정, 가변 작업, 목표, 주간 캘린더 화면
- 로그인 토큰 기반 API 호출
- 고정 일정 등록 시 `weekly` / `biweekly` 반복의 요일 선택 지원

### Backend / 백엔드

- FastAPI REST API
- 사용자, 고정 일정, 가변 작업, 목표, AI 계획, 자동 배정 관리
- Gemini API 기반 목표 분석, API 키가 없을 때 template fallback 사용
- 한글 목표 질문 생성 및 일정 품질 개선 질문 제공
- PostgreSQL + SQLAlchemy ORM + Alembic migration

## Tech Stack / 기술 스택

### Frontend

- Next.js 16
- React
- TypeScript
- Tailwind CSS
- Axios

### Backend

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Gemini API with template fallback

## Quick Start / 빠른 시작

### Prerequisites / 준비 사항

- Node.js 18+
- Python 3.12+
- Docker, PostgreSQL을 로컬로 실행할 경우 필요

### 1. Clone and Setup / 저장소 준비

```bash
git clone <repository-url>
cd now-what
```

### 2. Backend Setup / 백엔드 실행

```powershell
# Create virtual environment / 가상환경 생성
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies / 의존성 설치
pip install -r requirements.txt

# Copy environment variables / 환경 변수 파일 생성
Copy-Item .env.example .env

# Start PostgreSQL / PostgreSQL 실행
docker compose up -d

# Run migrations / DB 마이그레이션 실행
.\.venv\Scripts\alembic.exe upgrade head

# Start the API / API 서버 실행
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

API docs / API 문서:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Frontend Setup / 프론트엔드 실행

```bash
# Install dependencies / 의존성 설치
npm install

# Start development server / 개발 서버 실행
npm run dev
```

Frontend / 프론트엔드:

[http://localhost:3000](http://localhost:3000)

## Features / 주요 기능

### Schedule Management / 일정 관리

- Fixed schedule CRUD / 고정 일정 생성, 조회, 수정, 삭제
- Flexible task CRUD / 가변 작업 생성, 조회, 수정, 삭제
- Unified calendar view / 고정 일정과 자동 배정 작업을 함께 보는 캘린더
- `recurrence_rule` supports `daily`, `weekly`, `biweekly`, `monthly` / 반복 규칙은 `daily`, `weekly`, `biweekly`, `monthly`를 지원합니다.
- `weekly` and `biweekly` fixed schedules require `day_of_week` / 매주와 격주 반복 고정 일정은 `day_of_week` 요일 값이 필요합니다.
- `day_of_week` uses `0=Sunday`, `1=Monday`, ..., `6=Saturday` / `day_of_week`는 `0=일요일`, `1=월요일`, ..., `6=토요일`입니다.

### Goal Planning / 목표 계획

- Natural language goal intake / 자연어 목표 분석
- Korean goal questions / 한글 목표 질문 생성
- Schedule-quality questions / 좋은 일정 생성을 위한 질문 포함
  - `weekly_available_hours`: weekly realistic time budget / 일주일에 현실적으로 투자 가능한 시간
  - `preferred_work_times`: preferred focus windows / 집중하기 좋은 시간대
  - `unavailable_times`: blocked or bad time windows / 피해야 할 시간대
  - `session_preference`: short frequent sessions, balanced sessions, or long blocks / 짧게 자주, 보통 길이, 길게 몰아서 중 선호 방식
- Goal save + AI plan generation / 목표 저장과 AI 계획 생성
- Template fallback when Gemini is unavailable / Gemini 사용이 불가능할 때 템플릿 기반 응답 사용

### Allocation / 자동 배정

- Greedy allocation into available time / 빈 시간대에 작업 자동 배정
- Fixed schedules are preserved / 고정 일정과 겹치지 않도록 배정
- Existing auto allocations can be rebuilt / 기존 자동 배정을 다시 구성 가능
- Configurable day window, buffer, and daily cap / 하루 시작/종료 시간, 세션 간 버퍼, 일일 자동 배정 상한 설정 가능

## API Endpoints / 주요 API

Backend API inventory and capstone cleanup priorities are organized in [docs/backend-api-list.md](docs/backend-api-list.md).

Generated API reference is available at [docs/api-reference.md](docs/api-reference.md).

백엔드 API 목록과 정리 우선순위는 [docs/backend-api-list.md](docs/backend-api-list.md)에 정리되어 있습니다.

생성된 API reference는 [docs/api-reference.md](docs/api-reference.md)에서 확인할 수 있습니다.

### Main Endpoints / 주요 엔드포인트

- `POST /api/v1/users`: create user / 사용자 생성
- `POST /api/v1/users/login`: email login / 이메일 로그인
- `GET /api/v1/auth/me`: current user / 현재 사용자 확인
- `POST /api/v1/schedules/fixed`: create fixed schedule / 고정 일정 생성
- `GET /api/v1/schedules/fixed`: list fixed schedules / 고정 일정 조회
- `DELETE /api/v1/schedules/fixed/{schedule_id}`: delete fixed schedule / 고정 일정 삭제
- `POST /api/v1/tasks/flexible`: create flexible task / 가변 작업 생성
- `GET /api/v1/tasks/flexible`: list flexible tasks / 가변 작업 조회
- `DELETE /api/v1/tasks/flexible/{task_id}`: delete flexible task / 가변 작업 삭제
- `DELETE /api/v1/tasks/flexible/allocations/{allocation_id}`: remove allocated task slot / 배정된 작업 슬롯 삭제
- `POST /api/v1/goals/intake`: analyze goal and return questions / 목표 분석 및 질문 생성
- `POST /api/v1/goals/complete`: save goal and generate plan / 목표 저장 및 계획 생성
- `DELETE /api/v1/goals/{goal_id}`: delete goal and related plan data / 목표와 관련 계획 삭제
- `POST /api/v1/planner/allocate`: allocate tasks to schedule / 작업 자동 배정
- `DELETE /api/v1/planner/plan-items/{item_id}/schedule`: unschedule plan item / 계획 항목 일정 해제
- `POST /api/v1/planner/plan-items/{item_id}/skip`: skip plan item / 계획 항목 건너뛰기
- `GET /api/v1/calendar`: get unified calendar view / 통합 캘린더 조회

## Testing / 테스트

Run the backend test suite:

백엔드 테스트 전체 실행:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

Run frontend lint:

프론트엔드 lint 실행:

```bash
npm run lint
```

Run production build:

프로덕션 빌드 실행:

```bash
npm run build
```

`npm run build` uses `next/font` and may need network access to fetch Google Fonts.

`npm run build`는 `next/font`를 통해 Google Fonts를 가져오기 때문에 네트워크 접근이 필요할 수 있습니다.

### Current Test Coverage / 현재 테스트 커버리지

- Allocation behavior / 자동 배정 동작
- Timezone normalization in allocation / 자동 배정 시간대 정규화
- Delete endpoints for allocations, plan items, and goals / 배정, 계획 항목, 목표 삭제 API
- Auth ownership checks for token-scoped resources / 토큰 사용자 기준 리소스 소유권 검증
- Korean goal intake questions / 한글 목표 질문 생성
- Schedule-quality question keys / 일정 품질 개선 질문 키
- Fixed schedule recurrence validation / 고정 일정 반복 검증
- `weekly` / `biweekly` schedules requiring `day_of_week` / 매주, 격주 반복의 요일 필수 검증
- Korean recurrence aliases such as `매주` and `격주` / `매주`, `격주` 한글 반복 규칙 alias

## Environment / 환경 변수

Start from `.env.example`:

`.env.example`을 복사해 `.env`를 만든 뒤 필요한 값을 채웁니다.

```powershell
Copy-Item .env.example .env
```

Important settings / 주요 설정:

- `DATABASE_URL`: PostgreSQL connection string / PostgreSQL 연결 문자열
- `AUTO_CREATE_TABLES`: auto-create tables in local development only / 로컬 개발용 테이블 자동 생성 여부
- `SEED_DEMO_USER`: demo user seed option / 데모 사용자 생성 여부
- `DEFAULT_DAY_START`: default allocation day start / 자동 배정 기본 시작 시간
- `DEFAULT_DAY_END`: default allocation day end / 자동 배정 기본 종료 시간
- `DEFAULT_BUFFER_MINUTES`: default buffer between allocated sessions / 자동 배정 세션 간 기본 버퍼
- `DEFAULT_MAX_AUTO_MINUTES_PER_DAY`: daily auto-allocation cap / 하루 자동 배정 최대 시간
- `GEMINI_API_KEY`: Gemini API key / Gemini API 키
- `GOOGLE_CLIENT_ID`: Google OAuth client ID / Google OAuth 클라이언트 ID
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`: frontend Google OAuth client ID / 프론트엔드 Google OAuth 클라이언트 ID
- `ALLOWED_ORIGINS`: allowed frontend origins / 허용할 프론트엔드 origin 목록

## Database Schema / 데이터베이스 스키마

Main tables / 주요 테이블:

- `users`: user accounts / 사용자 계정
- `fixed_schedules`: fixed calendar events / 고정 일정
- `flexible_tasks`: tasks that can be scheduled flexibly / 가변 작업
- `goals`: user goals and answers / 목표와 답변
- `ai_plans`: AI-generated planning data / AI 생성 계획
- `ai_plan_items`: individual plan items / 개별 계획 항목
- `allocated_tasks`: scheduled task allocations / 자동 배정된 작업

Run migrations:

마이그레이션 실행:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

## Deployment / 배포

### Backend with Supabase / Supabase 백엔드

1. Replace `DATABASE_URL` in `.env` with your Supabase connection string.
2. Run migrations with `alembic upgrade head`.
3. Start the API with `uvicorn backend.main:app --reload`.

1. `.env`의 `DATABASE_URL`을 Supabase 연결 문자열로 교체합니다.
2. `alembic upgrade head`로 마이그레이션을 실행합니다.
3. `uvicorn backend.main:app --reload`로 API를 실행합니다.

### Frontend / 프론트엔드

```bash
npm run build
npm run start
```

## Notes / 참고

- Production defaults should keep `AUTO_CREATE_TABLES=false` and `SEED_DEMO_USER=false`.
- 운영 환경에서는 `AUTO_CREATE_TABLES=false`, `SEED_DEMO_USER=false`를 유지하는 것이 안전합니다.
- Most user data APIs require `Authorization: Bearer <access_token>`.
- 대부분의 사용자 데이터 API는 `Authorization: Bearer <access_token>` 인증이 필요합니다.
- Legacy request bodies may still include `user_id`, but authenticated backend routes should prefer the token user.
- 일부 legacy request body에는 `user_id`가 남아 있을 수 있지만, 인증 기반 백엔드 라우트는 토큰의 사용자를 우선합니다.
- `backend/` is the canonical FastAPI backend. The Next.js `app/` directory is frontend-only.
- `backend/`가 기준 FastAPI 백엔드입니다. Next.js `app/` 디렉터리는 프론트엔드 전용입니다.
- Local editor, backup, broken, build, and cache files are ignored by `.gitignore`.
- 로컬 에디터 설정, 백업 파일, broken 파일, 빌드 산출물, 캐시 파일은 `.gitignore`에서 제외합니다.
