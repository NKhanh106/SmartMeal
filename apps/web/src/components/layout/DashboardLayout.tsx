"use client";

import { useAuth } from "@/contexts/auth-context";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { Loader2 } from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans selection:bg-emerald-100 selection:text-emerald-900">
      <aside className="hidden w-[260px] md:block flex-shrink-0">
        <Sidebar className="fixed w-[260px]" />
      </aside>
      <div className="flex flex-col flex-grow min-w-0">
        <Header />
        <main className="flex-grow p-4 md:p-8 lg:p-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
