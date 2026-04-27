# ⚙️ SmartMeal Backend (FastAPI)

Thư mục này chứa toàn bộ mã nguồn của hệ thống Backend, chịu trách nhiệm xử lý nghiệp vụ, quản lý cơ sở dữ liệu và giao tiếp với các AI Providers (Google Gemini, Groq).

## 📂 Cấu trúc thư mục chi tiết

```text
apps/api/app/
├── ai/                # AI Layer - Tầng giao tiếp độc lập với các mô hình Trí tuệ nhân tạo
│   ├── providers/     # Chứa code thực thi cụ thể cho từng bên (Gemini, Groq...)
│   ├── prompts/       # Quản lý các prompt templates (Daily Planner, Meal Update...)
│   ├── base.py        # Interface chung `AIProvider` định nghĩa các hàm abstract bắt buộc
│   └── factory.py     # Nơi cấp phát AI provider động dựa trên file `.env`
│
├── api/v1/            # Các API Route chính của hệ thống, expose dữ liệu ra bên ngoài
│   ├── ai_chatbot.py  # Route điều phối logic của tính năng AI Coach Chatbot
│   ├── ai_daily_planner.py # Route sinh và trả về gợi ý lịch trình ngày mới
│   ├── dashboard.py   # Route thống kê số liệu Calo/Macros theo Ngày/Tuần
│   ├── food_nutrition.py # Route quản lý cơ sở dữ liệu thực phẩm chuẩn
│   ├── meal_logs.py   # Route CRUD lịch sử các bữa ăn trong ngày
│   ├── nutrition_goals.py # Route thiết lập và tính toán mục tiêu cá nhân
│   └── user_profiles.py # Route quản lý hồ sơ thể chất (cân nặng, chiều cao...)
│
├── chatbot/           # Module AI Coach độc lập (Tách biệt logic xử lý chat)
│   ├── context_builder.py # Engine trích xuất dữ liệu User, Goal, Meal từ Database thành Context
│   ├── context_policy.py  # Quy định giới hạn số lượng tin nhắn, số bữa ăn để tối ưu lượng token
│   ├── prompts.py         # File chứa System prompt định nghĩa vai trò của AI Coach
│   ├── service.py         # Chứa toàn bộ luồng tạo Session, lưu DB, gọi AI và xử lý log
│   └── utils.py           # Tiện ích bổ trợ nhỏ (VD: Cắt chuỗi tạo tự động tiêu đề chat)
│
├── core/              # Thành phần lõi vận hành ứng dụng
│   └── config.py      # Load & Validate các biến từ `.env` bằng công cụ Pydantic Settings
│
├── db/                # Khu vực thiết lập Cơ sở dữ liệu
│   └── session.py     # Chứa hàm khởi tạo kết nối `AsyncEngine` và `AsyncSession`
│
├── models/            # SQLAlchemy ORM Models (Sử dụng kiến trúc Mapped 2.0 mới nhất)
│   ├── ai_log.py      # Bảng `ai_analysis_logs`: Ghi nhận lịch sử gọi AI & Độ trễ (Latency)
│   ├── chat.py        # Bảng `chat_sessions` và `chat_messages`: Lưu tin nhắn
│   ├── daily_recommendation.py # Bảng `daily_recommendations`: Lưu kết quả Planner
│   ├── nutrition_goal.py # Bảng `nutrition_goals`: Chỉ tiêu Calo, Macro
│   ├── user_profile.py   # Bảng `user_profiles`: Thông tin sinh lý học
│   └── ...
│
├── schemas/           # Pydantic Schemas (Nhiệm vụ kiểm định dữ liệu Request/Response)
│   ├── chat.py        # Payload validation cho tin nhắn gửi lên AI
│   ├── daily_recommendation.py # Định dạng JSON response khi trả API Planner
│   ├── nutrition_goal.py # Payload dùng khi tính toán Macro/Calo
│   └── ...
│
└── services/          # Tầng Business Logic (Nơi chứa mọi phép tính và luồng vận hành)
    ├── ai_log_service.py # Dịch vụ lưu log cho AI xuống DB qua AsyncSession
    ├── daily_recommendation_service.py # Logic trích xuất context và gửi lên AI Planner
    ├── dashboard_service.py # Logic cộng dồn tổng Calo và Macros theo ngày/tuần
    └── nutrition_calculator.py # Các công thức y khoa (Mifflin-St Jeor, tính BMI...)
```

## 🧬 Tổng quan kiến trúc
Backend tuân thủ nghiêm ngặt mô hình phân lớp (Layered Architecture):
1. **API Router (`app/api`)**: Chỉ đóng vai trò điều phối, không chứa logic, nhận Request, gọi xuống tầng Service và trả kết quả.
2. **Service (`app/services`, `app/chatbot`)**: Trái tim của ứng dụng, chứa logic tính toán, xử lý nghiệp vụ, gọi truy vấn Database bất đồng bộ (AsyncSession).
3. **AI Layer (`app/ai`)**: Tầng Adapter gói gọn các SDK AI phức tạp thành một Interface chuẩn, dễ dàng thay thế giữa Gemini, Groq hoặc OpenAI mà không làm sụp cả hệ thống.
4. **Data Access**: Validate đầu vào bằng thư viện Pydantic siêu tốc độ và giao tiếp Database thông qua SQLAlchemy 2.0 (100% Asynchronous).
