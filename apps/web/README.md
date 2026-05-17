# SmartMeal Web — Frontend Application

## Mục đích

Đây là **frontend chính** của ứng dụng SmartMeal — một web app hiện đại cho phép người dùng quản lý dinh dưỡng, theo dõi bữa ăn, lập kế hoạch tập luyện, và tương tác với chatbot AI. Giao diện hỗ trợ **đa ngôn ngữ** (Tiếng Việt + English).

## Công nghệ sử dụng

| Category | Công nghệ | Giải thích |
|----------|-----------|------------|
| **Framework** | Next.js 15 (App Router) | React framework hiện đại với Server Components, routing file-based |
| **Language** | TypeScript 5 | Type safety toàn bộ codebase |
| **UI Library** | React 19 | Thư viện UI component |
| **Styling** | Tailwind CSS v4 | Utility-first CSS, responsive design |
| **Components** | shadcn/ui (Radix UI) | Component library đẹp, accessible, có thể tùy chỉnh |
| **State Management** | TanStack Query (React Query) | Server state: caching, background refetch, optimistic updates |
| **HTTP Client** | Axios | Gọi API backend với interceptors |
| **Forms** | React Hook Form + Zod | Form handling với validation |
| **Charts** | Recharts | Biểu đồ dinh dưỡng và analytics |
| **Animations** | Framer Motion | Smooth animations và transitions |
| **Icons** | Lucide React | Bộ icon đẹp, consistent |
| **Package Manager** | pnpm | Fast, efficient package manager |

## Cấu trúc thư mục

```
apps/web/
├── src/
│   ├── app/                    # Next.js App Router (pages & layouts)
│   │   ├── layout.tsx        # Root layout (providers, fonts)
│   │   ├── page.tsx          # Landing page
│   │   ├── (auth)/           # Auth routes (grouped)
│   │   │   ├── layout.tsx    # Auth layout
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   └── (dashboard)/      # Protected dashboard routes
│   │       ├── layout.tsx    # Dashboard layout (sidebar, header)
│   │       ├── dashboard/page.tsx
│   │       ├── upload/page.tsx
│   │       ├── history/page.tsx
│   │       ├── analytics/page.tsx
│   │       ├── goals/page.tsx
│   │       ├── workout/page.tsx
│   │       ├── recommendations/page.tsx
│   │       └── profile/page.tsx
│   ├── components/
│   │   ├── ui/              # shadcn/ui components (button, card, input, dialog,...)
│   │   ├── layout/          # Layout components
│   │   │   ├── Header.tsx  # Top navigation bar
│   │   │   ├── Sidebar.tsx  # Side navigation menu
│   │   │   └── DashboardLayout.tsx
│   │   └── chatbot/         # Chatbot UI
│   │       ├── FloatingChatBot.tsx  # Nút chatbot nổi (FAB)
│   │       ├── ChatPanel.tsx        # Panel chat chính
│   │       ├── ChatMessage.tsx      # Tin nhắn
│   │       ├── ChatMessageList.tsx   # Danh sách tin nhắn
│   │       ├── ChatInput.tsx        # Input nhập tin nhắn
│   │       ├── ChatBubble.tsx        # Chat bubble design
│   │       ├── ChatHeader.tsx       # Header của panel chat
│   │       └── types.ts              # TypeScript types cho chatbot
│   ├── contexts/
│   │   └── auth-context.tsx  # Auth state: user info, login/logout, redirect
│   ├── hooks/
│   │   └── use-chatbot.ts   # Custom hook để quản lý chatbot state
│   ├── lib/
│   │   ├── api-client.ts    # Axios instance, interceptors, error handling
│   │   ├── utils.ts         # Helper functions (cn(), formatDate,...)
│   │   └── profile-utils.ts  # Profile-related utilities
│   ├── providers/
│   │   ├── app-providers.tsx   # Main provider wrapper
│   │   └── query-provider.tsx  # TanStack Query provider
│   └── services/              # API service layer (typed API calls)
│       ├── auth.service.ts
│       ├── meal.service.ts
│       ├── profile.service.ts
│       ├── nutrition-goal.service.ts
│       ├── workout.service.ts
│       ├── progress-log.service.ts
│       ├── analytics.service.ts
│       ├── chatbot.service.ts
│       ├── recommendation.service.ts
│       └── health-service.ts
├── middleware.ts               # Next.js middleware (auth protection)
├── next.config.ts            # Next.js configuration
├── package.json             # Dependencies & scripts
├── tsconfig.json           # TypeScript config (path aliases: @/*)
├── tailwind.config.ts      # Tailwind CSS v4 config
├── postcss.config.js       # PostCSS config
└── components.json         # shadcn/ui config
```

## Routing

### Public Routes
| Route | Mô tả |
|-------|--------|
| `/` | Landing page — giới thiệu ứng dụng |
| `/login` | Trang đăng nhập |
| `/register` | Trang đăng ký |

### Protected Routes (Dashboard)
| Route | Mô tả |
|-------|--------|
| `/dashboard` | Trang chủ — tổng quan dinh dưỡng hôm nay |
| `/upload` | Upload ảnh thực phẩm để AI nhận diện |
| `/history` | Lịch sử bữa ăn |
| `/analytics` | Biểu đồ phân tích calo/macro |
| `/goals` | Thiết lập mục tiêu dinh dưỡng |
| `/workout` | Quản lý kế hoạch tập luyện |
| `/profile` | Thông tin cá nhân |
| `/recommendations` | Gợi ý từ AI |

## Authentication Flow

```
User visits protected route
    │
    ▼
Middleware checks cookie token
    │
    ├── No token? → Redirect /login
    │
    ├── Token exists? → Validate
    │       │
    │       ├── Valid → Show page
    │       └── Invalid/Expired → Redirect /login
    │
    ▼
AuthContext loads user info from API
```

## API Client Architecture

Axios client với interceptors:

```typescript
// Request interceptor: gắn auth token tự động
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: xử lý 401 → refresh token → retry
// Hoặc redirect về login nếu refresh fail
```

## State Management

### TanStack Query (Server State)
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['meals', date],
  queryFn: () => mealService.getMeals(date),
  staleTime: 5 * 60 * 1000, // 5 minutes
});
```

### Auth Context (Client State)
```typescript
const { user, login, logout, isAuthenticated } = useAuth();
```

## Chatbot System

Chatbot giao tiếp với backend qua streaming API:

```
User types message
    │
    ▼
POST /api/v1/ai/chat/sessions/{id}/messages/stream (SSE)
    │
    ▼
Backend → Groq AI → Streaming tokens → Frontend
    │
    ▼
Frontend renders streaming text in real-time
```

Frontend quản lý session qua `sessionStorage` để duy trì conversation history.

## Cách chạy

```bash
# Cài đặt dependencies
pnpm install

# Chạy development server
pnpm dev
# App: http://localhost:3000

# Build production
pnpm build

# Run linter
pnpm lint
```

## Responsive Design

| Breakpoint | Kích thước | Thiết bị |
|------------|------------|----------|
| `sm:` | >= 640px | Mobile landscape |
| `md:` | >= 768px | Tablet |
| `lg:` | >= 1024px | Desktop |
| `xl:` | >= 1280px | Large desktop |

## Environment Variables

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Best Practices

- Dùng TanStack Query cho tất cả API calls (không dùng useEffect)
- Luôn handle loading và error states
- Tách biệt UI components và business logic
- Dùng TypeScript types cho tất cả props và API responses
- Dùng shadcn/ui components thay vì custom nếu có sẵn
