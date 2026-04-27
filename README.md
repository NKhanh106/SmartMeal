# 🥗 SmartMeal - Trợ lý Dinh dưỡng & Luyện tập Cá nhân hóa bằng AI

SmartMeal là một hệ thống hỗ trợ dinh dưỡng và định hướng luyện tập cá nhân hóa. Bằng cách ứng dụng sức mạnh của **Google Gemini** kết hợp với cơ sở dữ liệu dinh dưỡng, SmartMeal đóng vai trò như một chuyên gia tư vấn (AI Coach) trực tuyến 24/7.

## 🌟 Tính năng cốt lõi
- **Hyper-Personalization**: Cá nhân hóa mục tiêu dinh dưỡng dựa trên TDEE, BMR, Macros và tình trạng thể chất (chiều cao, cân nặng, % mỡ, ...).
- **AI Meal Update (Computer Vision)**: Tự động phân tích và nhận diện món ăn, ước lượng calo/macros chỉ bằng hình ảnh thông qua hệ thống AI (Google Gemini).
- **AI Daily Planner**: Sinh gợi ý lịch trình ăn uống, luyện tập, và sinh hoạt cho ngày tiếp theo.
- **AI Coach Chatbot**: Trợ lý AI tương tác theo thời gian thực dựa trên bối cảnh dữ liệu thật của người dùng (Profile, Goal, Meal History, v.v.).

## 🏛 Kiến trúc Monorepo (Turborepo)
Dự án được cấu trúc theo dạng Monorepo sử dụng **Turborepo** và **pnpm**, giúp quản lý source code tập trung và tái sử dụng dễ dàng.

```text
SmartMeal/
├── apps/
│   ├── api/       # Backend (FastAPI, SQLAlchemy, PostgreSQL)
│   └── web/       # Frontend (Next.js 15, Tailwind, shadcn/ui)
├── packages/      # Các module dùng chung (config, types, ui...)
├── infra/         # Cấu hình hạ tầng (Docker, Nginx...)
├── docs/          # Tài liệu thiết kế hệ thống
└── README.md      # Tài liệu tổng quan dự án
```

## 🚀 Hướng dẫn cài đặt & Chạy dự án

### Yêu cầu hệ thống
- `Node.js` >= 20 và `pnpm` >= 9
- `Python` >= 3.12 (Khuyến nghị dùng Conda/Venv)
- `PostgreSQL` >= 15

### Khởi chạy Backend (API)
1. Đi tới thư mục API: `cd apps/api`
2. Cài đặt thư viện (nếu dùng requirements): `pip install -r requirements.txt` (Hoặc cài qua conda/pipenv).
3. Cấu hình môi trường: Sao chép `.env.example` thành `.env` và điền Database URI, `GEMINI_API_KEY`, `GROQ_API_KEY`.
4. Chạy server: `uvicorn app.main:app --reload`
5. Truy cập Swagger UI: `http://127.0.0.1:8000/docs`

### Khởi chạy Frontend (Web)
1. Tại thư mục gốc, cài đặt dependencies: `pnpm install`
2. Khởi chạy dev server: `pnpm dev --filter web`
3. Truy cập ứng dụng: `http://localhost:3000`
