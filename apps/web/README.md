# SmartMeal Web - Frontend Application

## Mục đích

Đây là **frontend chính** của ứng dụng SmartMeal - một web app hiện đại cho phép người dùng quản lý dinh dưỡng, theo dõi bữa ăn, lập kế hoạch tập luyện, và tương tác với chatbot AI.

## Công nghệ sử dụng

- **Framework**: Next.js 15 (App Router) - React framework với Server Components
- **UI Library**: Tailwind CSS v4 + shadcn/ui - Thiết kế đẹp, responsive
- **State Management**: TanStack Query (React Query) - Quản lý server state
- **HTTP Client**: Axios - Gọi API backend
- **Charts**: Recharts - Biểu đồ và visualizations
- **Forms**: React Hook Form + Zod - Form handling & validation
- **Animations**: Framer Motion - Smooth animations
- **Icons**: Lucide React - Bộ icon đẹp
- **Language**: TypeScript - Type safety

## Cấu trúc thư mục

```
apps/web/
├── src/
│   ├── app/                 # Next.js App Router (pages)
│   │   ├── (auth)/         # Authentication routes (login, register)
│   │   ├── (dashboard)/    # Protected dashboard routes
│   │   ├── layout.tsx      # Root layout
│   │   └── page.tsx        # Landing page
│   ├── components/         # React components
│   │   ├── chatbot/        # AI chatbot UI
│   │   ├── layout/         # Layout components
│   │   └── ui/             # shadcn/ui components
│   ├── contexts/           # React contexts
│   ├── hooks/              # Custom hooks
│   ├── lib/                # Utilities
│   ├── providers/          # App providers
│   ├── services/           # API services
│   └── data/               # Mock data
├── middleware.ts           # Next.js middleware (auth)
├── next.config.ts          # Next.js config
├── tailwind.config.ts      # Tailwind CSS config
└── package.json
```

## Các trang chính

### Public Pages
| Route | Mô tả |
|-------|-------|
| `/` | Landing page - giới thiệu ứng dụng |
| `/login` | Trang đăng nhập |
| `/register` | Trang đăng ký |

### Dashboard (Protected Routes)
| Route | Mô tả |
|-------|-------|
| `/dashboard` | Trang chủ dashboard - tổng quan |
| `/upload` | Upload ảnh thực phẩm |
| `/history` | Lịch sử bữa ăn |
| `/goals` | Thiết lập mục tiêu dinh dưỡng |
| `/workout` | Quản lý kế hoạch tập luyện |
| `/analytics` | Biểu đồ phân tích |
| `/profile` | Thông tin cá nhân |
| `/recommendations` | Đề xuất từ AI |

## Components

### Layout Components
- `Header.tsx` - Thanh header với navigation
- `Sidebar.tsx` - Sidebar menu
- `DashboardLayout.tsx` - Layout wrapper cho dashboard

### Chatbot Components
- `FloatingChatBot.tsx` - Nút chatbot nổi
- `ChatPanel.tsx` - Panel chat chính
- `ChatMessage.tsx` - Tin nhắn trong chat
- `ChatMessageList.tsx` - Danh sách tin nhắn
- `ChatInput.tsx` - Input để nhập tin nhắn
- `ChatBubble.tsx` - Bubble design cho messages

### UI Components (shadcn/ui)
Các components tái sử dụng được:
- `button.tsx` - Buttons
- `card.tsx` - Cards
- `input.tsx` - Input fields
- `dialog.tsx` - Dialogs/Modals
- `progress.tsx` - Progress bars
- `toast.tsx` - Toast notifications
- `badge.tsx` - Badges/Tags
- `avatar.tsx` - User avatars
- `table.tsx` - Tables
- `tabs.tsx` - Tabs
- `dropdown-menu.tsx` - Dropdown menus
- `sheet.tsx` - Slide-out panels

## Authentication Flow

```
User visits protected route
    ↓
Middleware checks auth token
    ↓
No token? → Redirect to /login
    ↓
Token exists? → Validate token
    ↓
Valid → Show page
Invalid/Expired → Redirect to /login
```

## State Management

### TanStack Query
Quản lý server state (API data):
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['meals', date],
  queryFn: () => mealService.getMeals(date),
  staleTime: 5 * 60 * 1000, // 5 minutes
});
```

### Auth Context
Quản lý client state (auth):
```typescript
const { user, login, logout, isAuthenticated } = useAuth();
```

## API Services

| Service | Mô tả |
|---------|-------|
| `auth.service.ts` | Đăng nhập, đăng ký, refresh token |
| `meal.service.ts` | CRUD meal logs |
| `profile.service.ts` | User profile |
| `nutrition-goal.service.ts` | Nutrition goals |
| `workout.service.ts` | Workout plans |
| `analytics.service.ts` | Dashboard analytics |
| `chatbot.service.ts` | AI chatbot |
| `recommendation.service.ts` | AI recommendations |
| `progress-log.service.ts` | Progress tracking |
| `health-service.ts` | Health check |
| `mockService.ts` | Mock data for development |

## API Client

Axios instance với interceptors:
```typescript
// Auto-add auth token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
    }
    return Promise.reject(error);
  }
);
```

## Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Cách chạy

```bash
# Cài đặt dependencies
pnpm install

# Chạy development server
pnpm dev

# Build production
pnpm build

# Run linter
pnpm lint
```

## Responsive Design

Ứng dụng hỗ trợ:
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

Tailwind breakpoints:
- `md:` - Tablet+
- `lg:` - Desktop+
