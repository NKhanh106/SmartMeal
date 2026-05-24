# Component Library

React components organized by feature domain. Built with TypeScript, Radix UI, and Tailwind CSS.

## Structure

```
components/
├── chat/            # Chat interface, message rendering
│   ├── ChatPanel.tsx
│   ├── ChatMessage.tsx
│   ├── ChatMessageList.tsx
│   ├── ChatHeader.tsx
│   ├── types.ts
│   └── cards/
│       ├── ChatCardContainer.tsx  # Card wrapper + SSE handler
│       ├── SingleSelectCard.tsx
│       ├── MultiSelectCard.tsx
│       ├── RankCard.tsx
│       ├── NumberInputCard.tsx
│       └── ConfirmCard.tsx
│
├── chatbot/         # Main chatbot widget
│   ├── ChatInput.tsx      # Text input with send button
│   ├── FloatingChatBot.tsx # Collapsible FAB button
│   └── types.ts
│
├── dashboard/       # Dashboard widgets
│   ├── StatCard.tsx       # Metric with progress bar
│   ├── MacroCard.tsx      # Protein/Carbs/Fat display
│   └── charts/            # Recharts wrappers
│
├── layout/         # Page layout
│   ├── Sidebar.tsx        # Navigation sidebar
│   ├── DashboardLayout.tsx # Sidebar + content wrapper
│   └── Header.tsx
│
├── profile/        # Profile wizard
│   └── ProfileCompletionIndicator.tsx
│
├── root/           # Error boundary
│   └── ErrorBoundary.tsx
│
└── ui/            # Base shadcn/ui components
    ├── button.tsx
    ├── card.tsx
    ├── input.tsx
    ├── badge.tsx
    ├── dialog.tsx
    ├── dropdown-menu.tsx
    ├── select.tsx
    ├── tabs.tsx
    ├── toast.tsx / Toaster.tsx
    ├── progress.tsx
    ├── label.tsx
    ├── table.tsx
    ├── avatar.tsx
    ├── scroll-area.tsx
    ├── separator.tsx
    ├── skeleton.tsx
    ├── sheet.tsx
    └── alert-dialog.tsx
```

## Design Principles

- **Compound components** for complex UI: `Card` = `CardHeader` + `CardContent` + `CardFooter`
- **`React.memo`** on list items (`ChatMessage`, `MealLogCard`) to prevent unnecessary re-renders when the list grows
- **Error boundaries** around all async data sections — the app never crashes due to a failed API call
- **Mobile-first:** all components verified at 375px viewport width
- **Radix UI primitives** for accessibility: keyboard navigation, focus management, screen reader support

## Interactive Card System

The chatbot uses an interactive card system to collect structured data from users. Five card types:

| Card Type | Trigger | User Action |
|-----------|---------|-------------|
| `single_select` | Choose one option | Click a radio-style option |
| `multi_select` | Choose multiple | Checkbox-style selection |
| `rank` | Order items | Drag to reorder |
| `number_input` | Enter a number | Type a value |
| `confirm` | Confirm/cancel | Yes/No buttons |

Cards are rendered by `ChatCardContainer`, which also handles the SSE `event: card` stream and dispatches to the appropriate card component. User responses are submitted back to the API via the chatbot service.

See `apps/api/app/agents/README.md` for the full card trigger system (when each card type fires).
