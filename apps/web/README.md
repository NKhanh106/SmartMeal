# 💻 SmartMeal Frontend (Next.js)

Thư mục này chứa ứng dụng giao diện người dùng (Client-side) của SmartMeal, mang lại trải nghiệm tương tác mượt mà, trực quan giúp người dùng dễ dàng cập nhật và theo dõi tiến trình cải thiện sức khỏe.

## 🛠 Công nghệ cốt lõi
- **Framework**: [Next.js 15](https://nextjs.org/) (App Router) - Hỗ trợ Server-side Rendering (SSR) giúp tối ưu tốc độ và SEO.
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) & [shadcn/ui](https://ui.shadcn.com/) - Xây dựng các UI element hiện đại, nhất quán, chuẩn Mobile-First.
- **Animation**: [Framer Motion](https://www.framer.com/motion/) - Hiệu ứng chuyển động cho các bảng điều khiển, thống kê để ứng dụng "sống động" hơn.
- **Data Fetching**: [TanStack Query](https://tanstack.com/query/latest) (React Query) - Quản lý trạng thái bất đồng bộ (Server State) và caching dữ liệu gọi từ Backend.
- **Charts**: [Recharts](https://recharts.org/) - Trực quan hóa dữ liệu dinh dưỡng (Biểu đồ Calo nạp vào, Tỉ lệ Macros...).

## 📂 Cấu trúc thư mục (App Router)

```text
apps/web/src/
├── app/               # Nơi cấu hình Router theo Next.js App Router (Layout, Page)
│   ├── dashboard/     # Màn hình chính (Tổng quan chỉ số, tiến trình theo tuần)
│   ├── chat/          # Giao diện màn hình nhắn tin trực tiếp với AI Coach
│   └── meal-log/      # Giao diện chức năng chụp ảnh món ăn và cập nhật thực đơn
│
├── components/        # Thư mục chứa các React Components độc lập, tái sử dụng cao
│   ├── ui/            # Các UI Kit cơ sở lấy từ shadcn (Button, Input, Card, Dialog...)
│   └── layout/        # Các thành phần cấu trúc khung ứng dụng (Header, Sidebar, Navbar...)
│
├── features/          # Các module tính năng phức tạp chia theo Domain
│   ├── chatbot/       # Các component đặc thù của tính năng AI Chatbot (MessageBubble...)
│   └── nutrition/     # Biểu đồ dinh dưỡng, form thiết lập/cập nhật mục tiêu Macros
│
├── hooks/             # Custom React Hooks (Ví dụ: useAuth, useDashboardData, useChat...)
├── lib/               # Các hàm tiện ích cấu hình lõi (Axios Client, hàm Utils format string...)
├── services/          # Nơi khai báo các hàm gọi API tương tác với Backend FastAPI
├── store/             # Quản lý Global State tĩnh phía Client (Zustand hoặc React Context)
└── types/             # Nơi khai báo các định nghĩa TypeScript Interfaces/Types
```

## 🚀 Tư duy tổ chức Code
- Ứng dụng áp dụng **Feature-Sliced Design** cơ bản: Các tính năng lớn được gói gọn trong thư mục `features/` để dễ maintain.
- Tách bạch giữa UI Components ngớ ngẩn (Dumb Components) ở `components/` và Components chứa logic (Smart Components) ở `features/`.
- Quản lý API Call tập trung tại `services/` giúp dễ dàng thay đổi endpoint khi cần.
