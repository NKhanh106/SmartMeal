# Thư mục `components/` — React Components

## Mục đích

Chứa toàn bộ **React components** được sử dụng trong ứng dụng SmartMeal.

## Cấu trúc

```
components/
├── ui/              # shadcn/ui base components — reusable primitives
├── layout/         # Layout components — Header, Sidebar, DashboardLayout
└── chatbot/        # Chatbot UI — FloatingChatBot, ChatPanel, ChatMessage,...
```

## UI Components (`ui/`)

Các base components từ shadcn/ui (Radix UI primitives):

| Component | Mô tả |
|-----------|--------|
| `button.tsx` | Nút bấm (multiple variants: default, outline, ghost, destructive) |
| `card.tsx` | Card container cho nội dung |
| `input.tsx` | Text input field |
| `dialog.tsx` | Modal dialog |
| `progress.tsx` | Progress bar (hiển thị % hoàn thành mục tiêu) |
| `toast.tsx` | Toast notifications (dùng thông qua Sonner) |
| `badge.tsx` | Tags/labels |
| `avatar.tsx` | User avatar |
| `table.tsx` | Table components |
| `tabs.tsx` | Tab navigation |
| `dropdown-menu.tsx` | Dropdown menu |
| `scroll-area.tsx` | Scrollable area |
| `sheet.tsx` | Slide-out panel |
| `skeleton.tsx` | Loading skeleton |
| `label.tsx` | Form label |
| `separator.tsx` | Horizontal/vertical divider |
| `toaster.tsx` | Toast provider (sử dụng Sonner) |

## Layout Components (`layout/`)

| Component | Mô tả |
|-----------|--------|
| `Header.tsx` | Top navigation bar với logo, user menu |
| `Sidebar.tsx` | Left sidebar navigation menu |
| `DashboardLayout.tsx` | Wrapper layout cho các trang dashboard |

## Chatbot Components (`chatbot/`)

| Component | Mô tả |
|-----------|--------|
| `FloatingChatBot.tsx` | FAB (Floating Action Button) — nút chatbot nổi ở góc phải màn hình |
| `ChatPanel.tsx` | Panel chat chính — chứa header, message list, input |
| `ChatMessage.tsx` | Wrapper cho một tin nhắn (user hoặc assistant) |
| `ChatMessageList.tsx` | Danh sách scrollable tất cả tin nhắn |
| `ChatInput.tsx` | Input để nhập tin nhắn (có nút gửi) |
| `ChatBubble.tsx` | Chat bubble design cho từng tin nhắn |
| `ChatHeader.tsx` | Header của chatbot panel (title, close button) |
| `types.ts` | TypeScript interfaces cho chatbot |

## Chatbot Architecture

```
FloatingChatBot (FAB button)
    │
    ▼ (onClick)
ChatPanel opens
    │
    ├── ChatHeader (title, close button)
    ├── ChatMessageList (scrollable messages)
    │   └── ChatMessage → ChatBubble
    └── ChatInput (text input + send button)
```

## Cách sử dụng Chatbot

```tsx
// FloatingChatBot được đặt trong app layout và luôn visible
<FloatingChatBot />

// Hoặc sử dụng ChatPanel trực tiếp trong một page
import { ChatPanel } from "@/components/chatbot/ChatPanel";
```

## Best Practices

- Dùng shadcn/ui components cho UI primitives thay vì custom components
- Layout components nhận props rõ ràng, có TypeScript types
- Chatbot components có internal state management (không cần external state)
- Luôn handle loading và error states trong UI components
