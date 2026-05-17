"use client";

import { useEffect, useState } from "react";

/**
 * Debounce a value by the given delay (default 300ms).
 * Returns the debounced value — useful for search inputs that trigger API calls.
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
