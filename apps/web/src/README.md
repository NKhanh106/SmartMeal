# `src/` — Frontend Source Code

Thư mục chứa toàn bộ source code của Next.js frontend.

## Cấu trúc

```
src/
├── app/              # Next.js App Router — pages và layouts
├── components/       # React components
│   ├── ui/          # shadcn/ui base components
│   ├── layout/      # Layout components (Sidebar, Header)
│   └── chatbot/     # Chatbot UI components
├── contexts/         # React Context providers
├── hooks/           # Custom React hooks
├── lib/             # Utilities (axios client, helpers)
├── providers/       # App-wide providers
├── services/        # API service layer
└── types/           # TypeScript type definitions
```

## Luồng dữ liệu

```
Component (page.tsx)
    │
    ▼ (React Query hooks)
Service Layer (services/*.ts)
    │
    ▼ (axios apiClient)
Backend API (/api/v1/...)
    │
    ▼ (SQLAlchemy + PostgreSQL)
Database
```

## Providers (providers/)

- **`app-providers.tsx`**: Wrapper chính — bao gồm QueryProvider + AuthProvider + Toaster + FloatingChatBot
- **`query-provider.tsx`**: TanStack Query provider (React Query) — caching, background refetch, optimistic updates

## Contexts (contexts/)

- **`auth-context.tsx`**: Auth state management — user info, login/logout/register, protected route redirect

## Luồng Auth

```
App loads
    │
    ├── Check localStorage for JWT token
    │   └── No token → show login page
    │   └── Has token → call GET /api/v1/auth/me
    │                   └── Success → set user, redirect to dashboard
    │                   └── Fail (401) → clear token, show login
    │
    ▼
AuthProvider wraps app
    │
    ▼
Protected routes redirect to /login if not authenticated
```

## Cấu hình

- **API base URL**: `NEXT_PUBLIC_API_BASE_URL` env var (default: `http://127.0.0.1:8000`)
- **JWT token**: stored in `localStorage` under key `smartmeal_access_token`
- **Axios interceptor**: tự động gắn `Authorization: Bearer <token>` vào mọi request
- **Axios error handling**: tự động parse FastAPI error format (422, 404, 401, v.v.)
