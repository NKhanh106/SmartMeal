# SmartMeal Web

Next.js 15 frontend for the SmartMeal platform.

## Technology

### Next.js 15 App Router

File-based routing with the App Router. Route groups organize public and authenticated routes:

```
(app)/          → Login, Register pages (no sidebar)
(dashboard)/    → All authenticated pages (sidebar layout)
```

Server Components fetch data, Client Components handle interactivity. The `layout.tsx` files wrap pages with providers (auth context, React Query, toast notifications).

### TanStack React Query v5

Server state management. All API data flows through React Query hooks in `src/hooks/`:

```typescript
// Query keys are centralized
export const DASHBOARD_QUERY_KEYS = {
  daily: (date) => ["dashboard", "daily", date] as const,
  weekly: (endDate) => ["dashboard", "weekly", endDate] as const,
  activeGoal: () => ["nutrition-goal", "active"] as const,
};

// Parallel fetching — one failure doesn't block others
export function useDashboardData() {
  const daily = useDailyDashboard();
  const weekly = useWeeklyDashboard();
  const goal = useActiveGoal();
  return { daily, weekly, goal, isLoading: ... };
}
```

Query invalidation triggers refetch after mutations (e.g., logging a meal invalidates the daily dashboard query).

### Tailwind CSS v4

Utility-first styling. Custom design tokens configured in the Tailwind config. Dark mode support via CSS variables.

### Radix UI + shadcn/ui

Headless accessible components built on Radix UI primitives. Components are copied into `src/components/ui/` from shadcn/ui and customized to match the project's design system.

### Framer Motion

Animations used purposefully:
- Chat messages: slide-in from bottom
- Typing indicator: pulsing dots
- Page transitions: fade
- Card interactions: spring-based hover effects

## Architecture

### Route Structure

```
src/app/
├── (auth)/
│   ├── login/
│   └── register/
│
├── (dashboard)/
│   ├── dashboard/     → Main overview with charts
│   ├── profile/       → 5-step profile wizard
│   ├── goals/         → Nutrition goal management
│   ├── meals/         → Meal log list + log form
│   ├── chat/          → Full chat interface
│   └── admin/         → Agent monitoring (admin only)
│
├── layout.tsx         → Root layout with providers
└── page.tsx          → Redirect to /dashboard or /login
```

### State Architecture

Three layers, each with a clear responsibility:

| Layer | Tool | What it manages |
|-------|------|-----------------|
| Server state | React Query | API data, caching, background refetch |
| Auth state | AuthContext | User, tokens, login/logout |
| UI state | `useState` within components | Local form state, modal open/close, selected tab |

### SSE Streaming

The chat SSE stream is consumed using the native browser `EventSource` API wrapped in a custom hook:

```typescript
// event: card → pendingCard state
// data: delta → append to message content
// data: [DONE] → setIsTyping(false)
// data: [ERROR] → show error toast
```

The hook manages the `EventSource` lifecycle (creation on send, cleanup on unmount) to prevent memory leaks.

## Directory Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── (auth)/            # Public auth pages
│   ├── (dashboard)/       # Protected dashboard pages
│   ├── layout.tsx         # Root layout + providers
│   └── page.tsx           # Root redirect
│
├── components/            # Reusable UI components
│   ├── chat/              # Chat interface, message list, cards
│   │   └── cards/         # 5 interactive card types
│   ├── chatbot/           # Chat input, types
│   ├── dashboard/         # Dashboard widgets (charts, stats)
│   ├── layout/           # Sidebar, header
│   ├── profile/          # Profile completion indicator
│   ├── root/              # Error boundary
│   └── ui/               # Base shadcn components
│
├── hooks/                 # Custom React hooks
│   ├── use-dashboard-queries.ts   # React Query hooks for dashboard
│   ├── use-chatbot.ts              # Chat state + SSE streaming
│   ├── use-debounce.ts              # Debounce utility
│   └── use-toast.ts                # Toast notifications
│
├── services/             # API client functions
│   ├── auth.service.ts
│   ├── analytics.service.ts
│   ├── chatbot.service.ts
│   └── ...
│
├── lib/                   # Utilities, constants, types
│   ├── api.ts            # Axios instance + interceptors
│   ├── constants.ts
│   └── types/
│
└── providers/            # Context providers
    ├── query-provider.tsx    # React Query setup
    └── auth-context.tsx      # Auth state
```
