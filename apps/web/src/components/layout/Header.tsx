"use client";

import { Bell, Search, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { MobileNav } from "./Sidebar";
import Link from "next/link";

function getInitials(name?: string | null, email?: string | null): string {
  if (name) {
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }
  if (email) return email[0].toUpperCase();
  return "JD";
}

export function Header() {
  const { user, isLoading } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-20 w-full items-center justify-between border-b bg-white/80 px-6 backdrop-blur-xl md:px-10">
      <div className="flex items-center gap-6">
        <MobileNav />
        <div className="hidden items-center gap-3 md:flex">
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-emerald-500 transition-colors" />
            <Input
              placeholder="Search health data..."
              className="h-10 w-[240px] lg:w-[320px] pl-10 border-slate-100 bg-slate-50/50 focus-visible:ring-emerald-500/20 focus-visible:bg-white transition-all rounded-xl"
            />
          </div>
        </div>
      </div>
      <div className="flex items-center gap-5">
        <Button
          variant="ghost"
          size="icon"
          className="relative text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 rounded-xl transition-all"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-emerald-500 border-2 border-white" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="relative h-10 w-10 rounded-full p-0 border-2 border-white shadow-sm ring-1 ring-slate-100 overflow-hidden hover:ring-emerald-200 transition-all"
            >
              <Avatar className="h-full w-full">
                {user ? (
                  <>
                    <AvatarFallback className="bg-emerald-100 text-emerald-700 font-bold text-sm">
                      {getInitials(user.full_name, user.email)}
                    </AvatarFallback>
                  </>
                ) : (
                  <AvatarFallback className="bg-slate-100 text-slate-400">
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "?"
                    )}
                  </AvatarFallback>
                )}
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-56 mt-2 rounded-xl border border-slate-100 shadow-xl shadow-slate-200/50 bg-white"
            align="end"
            forceMount
          >
            <DropdownMenuLabel className="font-normal p-4">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-bold leading-none text-slate-900">
                  {user?.full_name ?? "User"}
                </p>
                <p className="text-xs leading-none text-slate-500">
                  {user?.email ?? "—"}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-slate-50" />
            <div className="p-1">
              <DropdownMenuItem asChild className="rounded-lg cursor-pointer focus:bg-emerald-50 focus:text-emerald-700">
                <Link href="/profile">Profile</Link>
              </DropdownMenuItem>
              <DropdownMenuItem className="rounded-lg cursor-pointer focus:bg-emerald-50 focus:text-emerald-700">
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem className="rounded-lg cursor-pointer focus:bg-emerald-50 focus:text-emerald-700">
                Billing
              </DropdownMenuItem>
            </div>
            <DropdownMenuSeparator className="bg-slate-50" />
            <div className="p-1">
              <LogoutButton />
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

function LogoutButton() {
  const { logout } = useAuth();
  return (
    <button
      type="button"
      onClick={logout}
      className="w-full text-left rounded-lg cursor-pointer text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors flex items-center gap-2 px-2 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
    >
      Log out
    </button>
  );
}

