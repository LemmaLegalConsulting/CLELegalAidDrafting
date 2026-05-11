# Cleveland Legal Aid Drafting MVP

Agentic legal drafting MVP for Ohio landlord/tenant work. The app is structured around human-reviewed drafting: matter intake, candidate legal grounds, approved facts/sources, block-based drafting, validation, and DOCX export.

## Stack

- Django + Django Ninja API
- React + Lexical editor shell
- Postgres + pgvector for relational data and source chunk embeddings
- Redis + Celery for AI, OCR, validation, and export jobs
- Docker Compose for local parity with container deployment

## Quick Start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open:

- Backend API docs: http://localhost:8000/api/docs
- Django admin: http://localhost:8000/admin/
- Frontend: http://localhost:5173

Create database tables after the containers are up:

```powershell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Docker Desktop must be running before `docker compose up`. The backend is intended to run against Postgres because the initial migration enables the pgvector extension.

## Implemented MVP Surface

- Matter records with LegalServer-ready external IDs, problem codes, special problem codes, court, office, eviction ground, and subsidy metadata.
- Evidence, case notes, and claimable facts with verification status.
- Legal source and source chunk records with pgvector embeddings.
- Draft goals, candidate grounds, draft packages, draft blocks, and AI trace records.
- Stubbed motion-to-dismiss audit logic that proposes grounds from case signals.
- Django Ninja endpoints for matter selection, audit, ground review, draft package creation, and block editing.
- React/Lexical drafting workspace for reviewing the generated block package.

## Development Notes

The current AI behavior is intentionally stubbed and deterministic. Replace the service functions in `backend/core/services.py` with provider-backed agents as each workflow matures:

- matter audit
- legal source retrieval
- missing-fact questionnaire generation
- draft-plan generation
- block drafting
- citation/fact validation

Keep each AI call wrapped by `AITrace` so Legal Aid can audit model inputs, outputs, selected sources, and human review decisions.

## MVP Workflow

1. Create or sync a matter.
2. Select a drafting goal, such as `motion_to_dismiss`.
3. Run a matter audit to generate candidate grounds.
4. Advocate selects grounds, facts, and sources.
5. Generate a block-based draft plan.
6. Edit/review in the Lexical drafting surface.
7. Validate facts/citations and export.

This scaffold intentionally stores legal logic in database-backed objects instead of burying it in DOCX/Jinja templates. DOCX files should become layout shells; clauses, source rules, and use conditions should live in the app.
