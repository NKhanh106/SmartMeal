# Thư mục app/ - Next.js App Router Pages

## Mục đích

Chứa tất cả **pages/routes** của ứng dụng Next.js sử dụng App Router. Mỗi thư mục con tương ứng với một route trong URL.

## Cấu trúc App Router

```
src/app/
├── layout.tsx          # Root layout (áp dụng cho tất cả pages)
├── page.tsx            # Homepage (/)
├── (auth)/            # Auth route group
│   ├── login/
│   │   └── page.tsx   # /login
│   └── register/
│       └── page.tsx   # /register
└── (dashboard)/       # Protected route group
    ├── dashboard/
    │   └── page.tsx   # /dashboard
    ├── upload/
    │   └── page.tsx   # /upload
    ├── history/
    │   └── page.tsx   # /history
    ├── goals/
    │   └── page.tsx   # /goals
    ├── workout/
    │   └── page.tsx   # /workout
    ├── analytics/
    │   └── page.tsx   # /analytics
    ├── profile/
    │   └── page.tsx   # /profile
    └── recommendations/
        └── page.tsx   # /recommendations
```

## Route Groups

### (auth)
Nhóm các routes xác thực - không cần đăng nhập:
- `/login` - Trang đăng nhập
- `/register` - Trang đăng ký

### (dashboard)
Nhóm các routes dashboard - yêu cầu đăng nhập (protected):
- Tất cả routes bắt đầu bằng `/dashboard/...`

## Layouts

### Root Layout (`layout.tsx`)
Layout gốc được áp dụng cho toàn bộ app:
```typescript
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
```

### Dashboard Layout
Protected layout với sidebar và header:
```typescript
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Check auth
  // Show loading if needed
  // Render with DashboardLayout component
  return <DashboardLayout>{children}</DashboardLayout>;
}
```

## Server Components vs Client Components

### Server Components (default)
- Render ở server - tốt cho data fetching
- Không có interactivity
- Ví dụ: Dashboard overview page

```typescript
// Server Component - src/app/(dashboard)/dashboard/page.tsx
async function DashboardPage() {
  const data = await fetchDashboardData();
  return <DashboardContent data={data} />;
}
```

### Client Components (`"use client"`)
- Render ở client - có state và interactivity
- Dùng cho forms, buttons, animations

```typescript
"use client";

export function MealForm() {
  const [meals, setMeals] = useState([]);
  // Interactive code here
}
```

## Metadata

Mỗi page có thể định nghĩa metadata riêng:

```typescript
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard | SmartMeal",
  description: "Quản lý dinh dưỡng và sức khỏe",
};
```

## Data Fetching

### Server Side (Server Components)
```typescript
async function DashboardPage() {
  // Direct API call in server component
  const response = await fetch(`${API_URL}/api/v1/dashboard`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });
  
  const data = await response.json();
  return <Dashboard data={data} />;
}
```

### Client Side (TanStack Query)
```typescript
"use client";

export function MealList() {
  const { data, isLoading } = useQuery({
    queryKey: ['meals'],
    queryFn: () => mealService.getMeals()
  });
  
  if (isLoading) return <Skeleton />;
  return <MealListComponent meals={data} />;
}
```

## Navigation

### Link Component
```typescript
import Link from "next/link";

// Navigation
<Link href="/dashboard">Dashboard</Link>
<Link href="/upload">Upload</Link>
```

### useRouter
```typescript
import { useRouter } from "next/navigation";

const router = useRouter();
router.push("/dashboard");
router.back();
```

## Dynamic Routes

### Path Parameters
```typescript
// app/meals/[id]/page.tsx
export default function MealDetailPage({ 
  params 
}: { 
  params: { id: string } 
}) {
  return <div>Meal ID: {params.id}</div>;
}
```

### Search Params
```typescript
// app/meals/page.tsx
export default function MealsPage({
  searchParams
}: {
  searchParams: { page?: string; limit?: string }
}) {
  const page = parseInt(searchParams.page || "1");
  return <MealsList page={page} />;
}
```

## Error Handling

### Error Boundary
```typescript
// app/error.tsx
"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  );
}
```

### Not Found
```typescript
// app/not-found.tsx
export default function NotFound() {
  return (
    <div>
      <h2>Page Not Found</h2>
      <Link href="/">Go home</Link>
    </div>
  );
}
```

## Loading States

```typescript
// app/loading.tsx
export default function Loading() {
  return (
    <div className="flex items-center justify-center h-screen">
      <Spinner />
    </div>
  );
}
```
