# Custom React Hooks

Data-fetching and state logic extracted from components for reuse and testability.

## Hooks Reference

### `use-chatbot.ts` — Chat State Machine

The most complex hook. Manages the entire chat session lifecycle.

**Session management:**
- Loads the most recent session on mount (or creates a new one)
- Session switcher to view old conversations
- Creates new sessions with auto-generated titles

**SSE stream handling:**
```typescript
const eventSource = new EventSource(`/api/v1/chat/sessions/${sessionId}/messages/stream`);

// event: card → setPendingCard(card)
// data: delta → append to message content
// data: [DONE] → setIsTyping(false)
// data: [ERROR] → setError + toast
```

**Key state:**
```typescript
const [messages, setMessages] = useState<ChatMessage[]>([])
const [pendingCard, setPendingCard] = useState<ChatCard | null>(null)
const [isTyping, setIsTyping] = useState(false)
const [error, setError] = useState<string | null>(null)
```

**Optimistic updates:** User messages are added to the list immediately before the SSE stream starts. If the stream fails to start, the message is rolled back.

**EventSource cleanup:** The effect cleanup cancels the `EventSource` on unmount and when switching sessions, preventing memory leaks.

### `use-dashboard-queries.ts`

React Query hooks for dashboard data with centralized query keys and per-data-type `staleTime` settings.

| Hook | Data | staleTime | Reason |
|------|------|-----------|--------|
| `useDailyDashboard` | Daily nutrition | 2 min | Changes frequently |
| `useWeeklyDashboard` | 7-day summary | 10 min | Changes less often |
| `useActiveGoal` | Current goal | 30 min | Rarely changes |

```typescript
// Parallel loading — Promise.allSettled so one failure doesn't block others
export function useDashboardData() {
  const daily = useDailyDashboard();
  const weekly = useWeeklyDashboard();
  const goal = useActiveGoal();
  return {
    daily, weekly, goal,
    isLoading: daily.isLoading || weekly.isLoading || goal.isLoading,
  };
}
```

### `use-debounce.ts`

Simple debounce utility hook:

```typescript
const debouncedSearch = useDebouncedValue(searchInput, 300);
// debouncedSearch only updates 300ms after the last keystroke
```

### `use-toast.ts`

Wrapper around the `sonner` toast library for consistent toast notifications.

## Patterns Used

- **`useCallback`** for stable function references passed as event handlers to child components
- **`useEffect` cleanup** for `EventSource` cancellation (memory leak prevention)
- **`Promise.allSettled`** for parallel fetches where partial failure is acceptable
- **Error state + retry** pattern: each hook exposes `error` and `refetch()` for user-initiated retry
- **Query invalidation** after mutations to trigger immediate refetch of stale data
