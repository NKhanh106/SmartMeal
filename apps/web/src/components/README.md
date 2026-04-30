# components/ — React Components

Thư mục chứa tất cả React components được sử dụng trong ứng dụng.

## Cấu trúc

```
components/
├── ui/          # shadcn/ui atomic components (Button, Card, Input...)
├── layout/      # Layout components (Sidebar, Header, DashboardLayout)
└── chatbot/     # Chatbot UI components (ChatPanel, FloatingChatBot...)
```

## ui/ — Atomic Components

Các thành phần giao diện nguyên tử, xây dựng bằng **shadcn/ui** (Radix UI primitives + Tailwind CSS).

| Component | File | Mô tả |
|-----------|------|--------|
| `Button` | `ui/button.tsx` | Nút bấm với các variant: `default`, `outline`, `ghost`, `destructive`, `link` |
| `Card` | `ui/card.tsx` | Container card với CardHeader, CardContent, CardFooter |
| `Input` | `ui/input.tsx` | Input field chuẩn form |
| `Label` | `ui/label.tsx` | Label cho form inputs |
| `Badge` | `ui/badge.tsx` | Tag/label nhỏ |
| `Progress` | `ui/progress.tsx` | Thanh tiến trình |
| `Avatar` | `ui/avatar.tsx` | Avatar người dùng (hình tròn) |
| `Dialog` | `ui/dialog.tsx` | Modal dialog (Radix Dialog) |
| `DropdownMenu` | `ui/dropdown-menu.tsx` | Dropdown menu (Radix DropdownMenu) |
| `Sheet` | `ui/sheet.tsx` | Slide-in panel (mobile sidebar) |
| `Tabs` | `ui/tabs.tsx` | Tab navigation |
| `Table` | `ui/table.tsx` | Table components |
| `Separator` | `ui/separator.tsx` | Đường phân cách |
| `Skeleton` | `ui/skeleton.tsx` | Loading placeholder |
| `ScrollArea` | `ui/scroll-area.tsx` | Custom scroll area |
| `Toast` | `ui/toast.tsx` | Toast notification |
| `Toaster` | `ui/toaster.tsx` | Toast container (render trong root layout) |

## layout/ — Layout Components

Các component liên quan đến bố cục trang, chạy xuyên suốt ứng dụng.

| Component | File | Mô tả |
|-----------|------|--------|
| `Sidebar` | `layout/Sidebar.tsx` | Thanh điều hướng bên trái — logo, nav items với hover/active states |
| `Header` | `layout/Header.tsx` | Thanh header trên cùng — search, notifications, user avatar |
| `DashboardLayout` | `layout/DashboardLayout.tsx` | Layout wrapper — sidebar (260px) + content area, responsive (Sheet trên mobile) |

## chatbot/ — Chatbot UI

Các component xây dựng giao diện chatbot AI.

| Component | File | Mô tả |
|-----------|------|--------|
| `FloatingChatBot` | `chatbot/FloatingChatBot.tsx` | Nút bong bóng chat góc phải dưới màn hình — bật/tắt panel |
| `ChatPanel` | `chatbot/ChatPanel.tsx` | Panel chat chính — animation slide-up, shadow lớn |
| `ChatHeader` | `chatbot/ChatHeader.tsx` | Header của panel — tiêu đề "SmartMeal Coach", nút đóng |
| `ChatMessageList` | `chatbot/ChatMessageList.tsx` | Danh sách tin nhắn — auto-scroll xuống cuối |
| `ChatMessage` | `chatbot/ChatMessage.tsx` | Tin nhắn đơn lẻ — assistant (emerald avatar) hoặc user (slate avatar) |
| `ChatInput` | `chatbot/ChatInput.tsx` | Input nhập tin nhắn — textarea auto-resize, nút gửi |
| `ChatBubble` | `chatbot/ChatBubble.tsx` | Nút bong bóng chat — gradient emerald, icon Sparkles, pulse animation |
| `types` | `chatbot/types.ts` | Shared TypeScript types cho chatbot |

## Quy tắc

- **UI components** phải nhận props chuẩn, không hardcode business logic.
- **Không gọi API trực tiếp** trong components — dùng services.
- **Lucide React** là thư viện icons chính.
- Styles dùng **Tailwind CSS v4** với CSS variables từ `globals.css`.
