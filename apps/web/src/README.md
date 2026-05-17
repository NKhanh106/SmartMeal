# Thư mục `src/` — Frontend Source Code

## Mục đích

Đây là thư mục chứa toàn bộ source code của **Next.js 15** frontend. Tất cả React components, pages, services, và utilities đều nằm trong thư mục này.

## Cấu trúc

```
src/
├── app/              # Next.js App Router — pages & layouts (file-based routing)
├── components/       # React components (ui, layout, chatbot)
├── contexts/         # React Context providers (auth)
├── hooks/           # Custom React hooks
├── lib/             # Utilities (axios client, helpers)
├── providers/       # App-wide providers (query, app)
└── services/        # API service layer (typed API calls)
```

## Luồng dữ liệu

```
Component (page.tsx)
    │
    ▼ (TanStack Query hooks)
Service Layer (services/*.ts)
    │
    ▼ (axios apiClient)
Backend API (/api/v1/...)
    │
    ▼ (SQLAlchemy async + PostgreSQL)
Database
```

## Providers (`providers/`)

| Provider | File | Mô tả |
|----------|------|--------|
| AppProviders | `app-providers.tsx` | Wrapper chính: QueryProvider + AuthProvider + Toaster + FloatingChatBot |
| QueryProvider | `query-provider.tsx` | TanStack Query provider — caching, background refetch, optimistic updates |

## Contexts (`contexts/`)

| Context | File | Mô tả |
|---------|------|--------|
| AuthContext | `auth-context.tsx` | Auth state: user info, login/logout/register, protected route redirect |

## Luồng Authentication

```
App loads
    │
    ├── Check localStorage/cookies for JWT token
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

## Luồng Chatbot

```
User opens chatbot → FloatingChatBot
    │
    ▼
ChatPanel opens → ChatMessageList loads from sessionStorage
    │
    ▼
User types message → ChatInput
    │
    ▼
POST /api/v1/ai/chat/sessions/{id}/messages/stream (SSE)
    │
    ▼
Groq AI generates → tokens stream to frontend
    │
    ▼
Frontend renders streaming text in real-time
    │
    ▼
On complete → save full message to sessionStorage
```

## API Client (`lib/api-client.ts`)

Axios instance với:

```typescript
// 1. Base URL: NEXT_PUBLIC_API_BASE_URL (default: http://127.0.0.1:8000)
// 2. Request interceptor: gắn Authorization: Bearer <token>
// 3. Response interceptor: handle 401 → refresh → retry, hoặc redirect /login
// 4. Error handling: parse FastAPI error format (422, 404, 401, 503)
// 5. Typed helpers: api.get, api.post, api.put, api.patch, api.delete, api.uploadFile
```

## Cấu hình TypeScript

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  }
}
```

Tất cả imports có thể dùng `@/` thay vì relative paths:

```typescript
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
```

## Custom Hooks (`hooks/`)

| Hook | File | Mô tả |
|------|------|--------|
| useChatbot | `use-chatbot.ts` | Custom hook quản lý chatbot state, streaming, session |

## Cách thêm API Service mới

1. Tạo file trong `services/`, ví dụ: `my-service.ts`
2. Define TypeScript interfaces cho request/response
3. Export các async functions dùng `api.get/post/put/delete`
4. Đăng ký query keys trong TanStack Query

```typescript
// services/my-service.ts
export const myService = {
  async getData(id: string): Promise<MyData> {
    return api.get<MyData>(`/my-endpoint/${id}`);
  }
};
```

## Best Practices

- **Dùng TanStack Query** cho tất cả API calls — không dùng `useEffect`
- Luôn **handle loading và error states** trong components
- Tách biệt **UI components** và **business logic**
- Dùng **TypeScript types** cho tất cả props và API responses
- Dùng **shadcn/ui components** thay vì custom nếu có sẵn
- Import path aliases (`@/`) thay vì relative paths khi có thể
