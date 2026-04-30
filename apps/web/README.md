# 💻 SmartMeal Frontend — Next.js 15

## Tổng quan

Frontend của SmartMeal được viết bằng **Next.js 15** (App Router) với **TypeScript**. Giao diện sử dụng **Tailwind CSS v4** và **shadcn/ui** (Radix UI primitives), quản lý server state bằng **TanStack Query**.

> **Trạng thái**: Hiện tại đang ở giai đoạn **scaffold** — backend connection test page đã hoạt động, UI components cơ bản đã setup. Các trang tính năng (dashboard, meal-log, chat...) cần phát triển thêm.

---

## Cấu trúc thư mục

```
apps/web/src/
├── app/                       # App Router — file-based routing
│   ├── layout.tsx             # Root layout: QueryProvider, Toaster, html lang="vi"
│   ├── page.tsx              # Backend connection test page (/)
│   ├── globals.css           # Tailwind v4 @theme definitions
│   │
│   ├── dashboard/            # [TODO] Trang tổng quan: biểu đồ calo/macro tuần
│   ├── meal-log/             # [TODO] Ghi nhận bữa ăn, chụp ảnh món ăn
│   ├── chat/                 # [TODO] Giao diện AI Coach Chatbot
│   ├── profile/              # [TODO] Hồ sơ người dùng
│   ├── goals/                # [TODO] Thiết lập mục tiêu dinh dưỡng
│   ├── workout/              # [TODO] Kế hoạch tập luyện
│   └── auth/                 # [TODO] Login / Register pages
│
├── components/               # React components
│   └── ui/                   # shadcn/ui components (14 components hiện tại)
│       ├── avatar.tsx
│       ├── badge.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── dropdown-menu.tsx
│       ├── input.tsx
│       ├── label.tsx
│       ├── progress.tsx
│       ├── separator.tsx
│       ├── skeleton.tsx
│       ├── tabs.tsx
│       ├── toast.tsx
│       └── toaster.tsx
│
├── hooks/                    # Custom React Hooks
│   └── use-toast.ts          # Hook cho toast notifications
│
├── lib/                      # Core utilities & configurations
│   ├── utils.ts              # cn() — clsx + tailwind-merge helper
│   └── api-client.ts         # Axios instance với JWT interceptors
│
├── providers/                 # Context providers (client components)
│   └── query-provider.tsx    # TanStack Query provider
│
├── services/                 # API service functions (gọi backend)
│   └── health-service.ts     # getHealth() — test backend connectivity
│
└── features/                 # [TODO] Feature-sliced modules (complex domain logic)
    ├── auth/                 # Auth forms, login/register UI
    ├── dashboard/            # Dashboard components & hooks
    ├── meal-log/             # Meal logging components
    ├── chatbot/              # Chatbot UI (MessageBubble, ChatInput...)
    └── nutrition/            # Nutrition charts, goal forms
```

---

## Công nghệ & Thư viện

| Thư viện | Phiên bản | Mục đích |
|----------|-----------|-----------|
| **Next.js** | 15.2.4 | Framework, App Router, SSR/SSG |
| **React** | 19.0.0 | UI library |
| **TypeScript** | 5.8 | Type safety |
| **Tailwind CSS** | 4.1.4 | Utility-first CSS (v4, dùng `@theme` trong CSS) |
| **shadcn/ui** | — | Radix UI + Tailwind components |
| **TanStack Query** | 5.72.2 | Server state management, caching |
| **Axios** | 1.8.4 | HTTP client cho API calls |
| **React Hook Form** | 7.55 | Form state management |
| **Zod** | 3.24.2 | Runtime schema validation |
| **Framer Motion** | 12.6.3 | Animations & transitions |
| **Recharts** | 2.15.2 | Charts (biểu đồ calo, macros) |
| **Lucide React** | 0.487 | Icons |

---

## API Client

### Cấu hình

`apps/web/src/lib/api-client.ts` — Axios instance:

- **Base URL**: từ `NEXT_PUBLIC_API_BASE_URL` (`.env.local`)
- **Timeout**: 30 giây
- **Request Interceptor**: tự động gắn `Authorization: Bearer <token>` từ `localStorage`
- **Response Interceptor**: nếu HTTP 401 → xóa token khỏi `localStorage`

### JWT Token Storage

- Token được lưu trong `localStorage` với key `smartmeal_access_token`
- Các request tự động attach token (không cần manual)
- Khi backend trả 401 → interceptor tự động xóa token và redirect về login

### Ví dụ gọi API

```typescript
// apps/web/src/services/health-service.ts
import { apiClient } from '@/lib/api-client';

export async function getHealth() {
  const res = await apiClient.get('/health');
  return res.data;
}
```

---

## Environment Variables

Tạo file `apps/web/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

> **Lưu ý**: Chỉ biến có prefix `NEXT_PUBLIC_` mới được expose ra browser. API base URL cần public vì dùng ở client-side.

---

## Các lệnh

```bash
cd apps/web

pnpm dev          # Dev server (Next.js 15, Turbopack)
pnpm build        # Production build
pnpm start        # Chạy production server
pnpm lint         # ESLint
```

---

## Tailwind CSS v4 — Cách cấu hình

Tailwind v4 không dùng `tailwind.config.ts`. Thay vào đó, cấu hình trong CSS:

```css
/* apps/web/src/app/globals.css */
@import "tailwindcss";

@theme {
  --color-background: #ffffff;
  --color-foreground: #09090b;
  --radius-lg: 0.5rem;
  /* ... tất cả CSS variables cho shadcn/ui */
}
```

---

## shadcn/ui — Thêm component mới

```bash
# Cài đặt shadcn/ui CLI
npx shadcn@latest init

# Thêm component mới
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add dialog
```

Component mới sẽ được tạo trong `src/components/ui/`. File `components.json` chứa cấu hình shadcn (style, base color, aliases...).

---

## Cấu hình TypeScript Path Aliases

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

→ `@/` map đến `./src/`, ví dụ: `@/lib/utils`, `@/components/ui/button`, `@/services/health-service`

---

## Backend Connection Test

Trang test backend (`apps/web/src/app/page.tsx`):

1. Gọi `GET /health` qua `getHealth()` service
2. Hiển thị loading spinner (shadcn `Card` + `Button`)
3. Nếu thành công → hiển thị JSON response từ backend
4. Nếu lỗi → hiển thị thông báo lỗi

Sau khi backend chạy ở `http://127.0.0.1:8000`, mở `http://localhost:3000` để test.

---

## TODO — Các tính năng cần phát triển tiếp

### Ưu tiên cao

- [ ] **Auth pages** — Login, Register, Forgot Password UI
- [ ] **Profile page** — Form nhập chiều cao, cân nặng, ngày sinh...
- [ ] **Goals page** — Form đặt mục tiêu dinh dưỡng
- [ ] **Meal Log page** — Ghi nhận bữa ăn thủ công, tìm kiếm thực phẩm
- [ ] **AI Meal Update UI** — Chụp ảnh / upload ảnh món ăn, preview kết quả AI

### Ưu tiên trung bình

- [ ] **Dashboard page** — Biểu đồ calo/macro tuần (Recharts)
- [ ] **Workout page** — Kế hoạch tập luyện, danh sách bài tập
- [ ] **Progress Logs page** — Nhật ký cân nặng, % mỡ, ảnh tiến bộ
- [ ] **AI Daily Planner page** — Xem gợi ý ngày mới từ AI

### Ưu tiên thấp

- [ ] **AI Chatbot UI** — Giao diện chat với AI Coach (message bubbles, input)
- [ ] **Settings page** — Đổi mật khẩu, cài đặt tài khoản
- [ ] **Admin page** — Quản lý food nutrition database (verify foods)

---

## ESLint & Code Quality

```bash
pnpm lint  # Chạy ESLint (next/core-web-vitals + next/typescript)
```

ESLint config tại `.eslintrc.json` extend `next/core-web-vitals` và `next/typescript`.
