# SmartMeal - Workspace Architecture Guide

Tai lieu nay mo ta cau truc workspace theo huong production cho SmartMeal.

## Cau truc tong the

```text
smartmeal-workspace/
├─ apps/
│  ├─ web/                        # Frontend Next.js
│  │  ├─ public/
│  │  ├─ src/
│  │  │  ├─ app/                  # App Router
│  │  │  ├─ components/           # UI components dùng riêng cho web
│  │  │  ├─ features/             # Theo domain: auth, meal, profile, plan...
│  │  │  ├─ hooks/
│  │  │  ├─ lib/                  # fetcher, utils, config client
│  │  │  ├─ services/             # gọi API backend
│  │  │  ├─ store/                # client state nếu cần
│  │  │  ├─ styles/
│  │  │  ├─ types/
│  │  │  └─ middleware.ts
│  │  ├─ tests/
│  │  ├─ package.json
│  │  └─ next.config.ts
│  │
│  └─ api/                        # Backend FastAPI
│     ├─ app/
│     │  ├─ api/                  # routers / versioning
│     │  │  ├─ v1/
│     │  │  │  ├─ endpoints/
│     │  │  │  └─ router.py
│     │  ├─ core/                 # config, security, settings, logging
│     │  ├─ db/                   # session, base, migration helpers
│     │  ├─ models/               # ORM models
│     │  ├─ schemas/              # Pydantic request/response schemas
│     │  ├─ repositories/         # data access layer
│     │  ├─ services/             # business logic
│     │  ├─ integrations/         # Gemini, USDA, email, storage...
│     │  ├─ ai/                   # prompt builders, parsers, tool calling
│     │  ├─ domain/               # nutrition, user-goal, workout rules
│     │  ├─ utils/
│     │  ├─ workers/              # background jobs
│     │  ├─ main.py
│     │  └─ dependencies.py
│     ├─ tests/
│     ├─ alembic/
│     ├─ pyproject.toml
│     └─ Dockerfile
│
├─ packages/
│  ├─ shared-types/               # DTO docs, OpenAPI typings, constants dùng chung
│  ├─ ui/                         # shared UI library nếu sau này có mobile/admin
│  ├─ config-eslint/
│  ├─ config-typescript/
│  └─ docs-snippets/
│
├─ docs/
│  ├─ architecture/
│  ├─ api/
│  ├─ database/
│  ├─ deployment/
│  ├─ onboarding/
│  ├─ adr/                        # Architecture Decision Records
│  └─ conventions/
│
├─ infra/
│  ├─ docker/
│  ├─ nginx/
│  ├─ scripts/
│  ├─ monitoring/
│  └─ compose/
│
├─ .github/
│  └─ workflows/
├─ .env.example
├─ Makefile
├─ README.md
├─ pnpm-workspace.yaml
└─ turbo.json                     # hoặc nx.json nếu dùng Nx
```

## Nguyen tac cot loi

- Frontend va backend tach biet ro rang.
- Backend la trung tam nghiep vu, AI, database va integrations.
- Dung monorepo de quan ly workspace, docs, CI/CD va config nhat quan.
- Tach integrations, repositories, services, schemas, models de de bao tri.
- Tai lieu ky thuat phai song hanh voi source code.
