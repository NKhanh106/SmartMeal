# Thư mục components/ - React Components

## Mục đích

Chứa tất cả **React components** được sử dụng trong ứng dụng SmartMeal Web. Components được tổ chức theo chức năng để dễ dàng tìm kiếm và quản lý.

## Cấu trúc

```
components/
├── chatbot/           # AI Chatbot UI components
│   ├── ChatPanel.tsx
│   ├── FloatingChatBot.tsx
│   ├── ChatMessage.tsx
│   ├── ChatMessageList.tsx
│   ├── ChatInput.tsx
│   ├── ChatBubble.tsx
│   └── ChatHeader.tsx
├── layout/           # Layout components
│   ├── Header.tsx
│   ├── Sidebar.tsx
│   └── DashboardLayout.tsx
└── ui/               # shadcn/ui base components
    ├── button.tsx
    ├── card.tsx
    ├── input.tsx
    ├── dialog.tsx
    ├── progress.tsx
    ├── toast.tsx
    ├── badge.tsx
    ├── avatar.tsx
    ├── table.tsx
    ├── tabs.tsx
    ├── dropdown-menu.tsx
    ├── scroll-area.tsx
    ├── sheet.tsx
    ├── skeleton.tsx
    ├── label.tsx
    └── separator.tsx
```

## Component Categories

### 1. Layout Components

#### Header.tsx
Thanh header chính của ứng dụng:
- Logo và app name
- Navigation links
- User avatar dropdown
- Notification bell
- Mobile hamburger menu

#### Sidebar.tsx
Thanh sidebar cho dashboard:
- Navigation menu items
- Active state highlighting
- Collapsible on mobile
- Icons cho mỗi menu item

#### DashboardLayout.tsx
Wrapper layout cho tất cả dashboard pages:
- Header at top
- Sidebar on left
- Main content area
- Responsive design

### 2. Chatbot Components

#### FloatingChatBot.tsx
Nút chatbot nổi ở góc màn hình:
- Floating action button
- Opens ChatPanel on click
- Badge showing unread messages
- Animation on hover

#### ChatPanel.tsx
Panel chat chính:
- Chat header với close button
- Message list area
- Input area
- Typing indicator
- Auto-scroll to latest message

#### ChatMessage.tsx
Hiển thị một tin nhắn:
- User message (right side)
- Assistant message (left side)
- Timestamp
- Avatar
- Different styles for user/assistant

#### ChatMessageList.tsx
Danh sách tin nhắn:
- Scrollable container
- Auto-scroll to bottom
- Virtual scrolling for long lists
- Date separators

#### ChatInput.tsx
Input để nhập tin nhắn:
- Text input
- Send button
- Loading state
- Character counter

#### ChatBubble.tsx
Design cho bubble tin nhắn:
- Rounded corners
- User vs Assistant styling
- Max width constraint
- Word wrap

#### ChatHeader.tsx
Header của chat panel:
- Title "SmartMeal Assistant"
- Status indicator
- Minimize/Close buttons

### 3. UI Components (shadcn/ui)

Đây là các base components được cung cấp bởi [shadcn/ui](https://ui.shadcn.com/), một collection của reusable components được xây dựng trên Radix UI và Tailwind CSS.

#### button.tsx
```typescript
<Button variant="default" size="default">Click me</Button>
// Variants: default, destructive, outline, secondary, ghost, link
// Sizes: default, sm, lg, icon
```

#### card.tsx
```typescript
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Description</CardDescription>
  </CardHeader>
  <CardContent>Content</CardContent>
  <CardFooter>Footer</CardFooter>
</Card>
```

#### input.tsx
```typescript
<Input placeholder="Enter text..." />
```

#### dialog.tsx
```typescript
<Dialog>
  <DialogTrigger>Open</DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Title</DialogTitle>
    </DialogHeader>
    Content here
  </DialogContent>
</Dialog>
```

#### progress.tsx
```typescript
<Progress value={50} />
```

#### toast.tsx
```typescript
// Using useToast hook
const { toast } = useToast();
toast({ title: "Success", description: "Meal logged!" });
```

#### badge.tsx
```typescript
<Badge variant="default">New</Badge>
// Variants: default, secondary, destructive, outline
```

#### avatar.tsx
```typescript
<Avatar>
  <AvatarImage src="/avatar.jpg" />
  <AvatarFallback>JD</AvatarFallback>
</Avatar>
```

## Component Patterns

### Server vs Client Components

**Server Component** (không có "use client"):
```typescript
// Header.tsx - Server component
export function Header() {
  return <header>...</header>;
}
```

**Client Component** (có "use client"):
```typescript
"use client";
// ChatPanel.tsx - Client component với state
export function ChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  // ...
}
```

### Component Composition

```typescript
// Reusable wrapper
export function Card({ 
  children, 
  className 
}: { 
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border bg-card", className)}>
      {children}
    </div>
  );
}

// Usage
<Card className="p-4">
  <h2>Title</h2>
  <p>Content</p>
</Card>
```

### TypeScript Props

```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline";
  size?: "default" | "sm" | "lg";
  isLoading?: boolean;
}

export function Button({
  children,
  variant = "default",
  size = "default",
  isLoading = false,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(styles[variant], styles[size], className)}
      disabled={isLoading || props.disabled}
      {...props}
    >
      {isLoading ? <Spinner /> : children}
    </button>
  );
}
```

## Styling với Tailwind CSS

Components sử dụng Tailwind CSS cho styling:
- `cn()` utility để merge classnames
- CSS variables cho theming
- Responsive classes (sm:, md:, lg:)
- Dark mode support

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Usage
<div className={cn(
  "p-4",
  isActive && "bg-primary",
  className
)} />
```

## Accessibility

Tất cả components tuân thủ WCAG guidelines:
- Semantic HTML
- ARIA labels
- Keyboard navigation
- Focus management
- Screen reader support

## Best Practices

1. **Colocation**: Giữ component files cùng với related files
2. **Small components**: Tách nhỏ components khi có thể
3. **Props types**: Luôn định nghĩa TypeScript types cho props
4. **Default exports**: Ưu tiên named exports
5. **Single responsibility**: Mỗi component nên làm một việc
