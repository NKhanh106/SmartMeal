# Thư mục `lib/` — Utilities & API Client

## Mục đích

Chứa các **tiện ích dùng chung** cho toàn bộ frontend: Axios HTTP client, helper functions, và utilities cho profile.

## Các thành phần

### `api-client.ts` — HTTP Client

Axios instance đã được cấu hình sẵn với interceptors:

```typescript
import { api } from "@/lib/api-client";

// Typed request helpers
const data = await api.get<User[]>("/api/v1/users");
const result = await api.post<AuthResponse>("/api/v1/auth/login", { email, password });
const formData = new FormData();
formData.append("file", file);
const uploaded = await api.uploadFile<ImageResponse>("/api/v1/uploads", formData);
```

**Tính năng:**

1. **Request Interceptor**: Tự động gắn `Authorization: Bearer <token>` từ localStorage
2. **Response Interceptor**: Xử lý 401 → thử refresh token → retry hoặc redirect `/login`
3. **Error Handling**: Parse error từ nhiều format khác nhau:
   - `{ detail: string }` — FastAPI error thông thường
   - `{ detail: [...] }` — FastAPI 422 Zod validation errors
   - `{ message: string }` — Generic error
4. **AbortSignal support**: Hỗ trợ hủy request bằng AbortController
5. **File Upload**: Wrapper đặc biệt cho multipart/form-data (tự tính boundary)

**Token Management:**
```typescript
// Lưu trong localStorage
localStorage.getItem("smartmeal_access_token");
localStorage.getItem("smartmeal_refresh_token");

// Đồng bộ với cookies cho SSR
document.cookie = `access_token=${token}; path=/; max-age=${expires_in}; SameSite=Lax`;
```

### `utils.ts` — Helper Functions

Các utility functions dùng chung:

```typescript
import { cn } from "@/lib/utils";

// Classname utility (clsx + tailwind-merge)
const className = cn("px-4 py-2", isActive && "bg-primary");

// Các helper khác: formatDate, formatNumber, debounce...
```

### `profile-utils.ts` — Profile Utilities

Các hàm tiện ích liên quan đến profile:

```typescript
// Tính BMI
import { calculateBMI } from "@/lib/profile-utils";

// Tính BMR (Mifflin-St Jeor)
import { calculateBMR } from "@/lib/profile-utils";

// Định dạng số đo cơ thể
import { formatMeasurement } from "@/lib/profile-utils";
```

## Best Practices

- Luôn dùng `api.get/post/put/patch/delete` thay vì gọi `axios` trực tiếp
- Dùng `cn()` (classnames utility) thay vì template string cho className
- Đặt types cho mọi API response để tận dụng TypeScript
- Import từ `@/` alias thay vì relative paths
