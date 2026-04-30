"use client";

import { QueryProvider } from "@/providers/query-provider";
import { AuthProvider } from "@/contexts/auth-context";
import { Toaster } from "@/components/ui/toaster";
import { FloatingChatBot } from "@/components/chatbot/FloatingChatBot";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <AuthProvider>
        {children}
        <Toaster />
        <FloatingChatBot />
      </AuthProvider>
    </QueryProvider>
  );
}
