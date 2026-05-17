"use client";

import React, { useState, memo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  Target,
  Camera,
  History,
  BarChart2,
  Zap,
  Dumbbell,
  LogOut,
  Menu,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";

interface NavItem {
  title: string;
  href: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Health Profile", href: "/profile", icon: User },
  { title: "Nutrition Goals", href: "/goals", icon: Target },
  { title: "Upload Meal", href: "/upload", icon: Camera },
  { title: "Meal History", href: "/history", icon: History },
  { title: "Analytics", href: "/analytics", icon: BarChart2 },
  { title: "Recommendations", href: "/recommendations", icon: Zap },
  { title: "Workout Plan", href: "/workout", icon: Dumbbell },
];

const adminNavItems: NavItem[] = [
  { title: "Agent Monitor", href: "/admin/agents", icon: Shield, adminOnly: true },
];

const Sidebar = memo(function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const visibleNavItems = [
    ...navItems,
    ...(isAdmin ? adminNavItems : []),
  ];

  return (
    <div
      className={cn(
        "pb-12 h-screen border-r bg-card flex flex-col",
        className
      )}
    >
      <div className="p-6">
        <Link href="/dashboard" className="flex items-center gap-3 mb-10 cursor-pointer">
          <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center text-white font-bold text-lg">
            S
          </div>
          <span className="font-extrabold text-xl tracking-tight">SmartMeal</span>
        </Link>

        <nav className="space-y-1">
          {visibleNavItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-all hover:bg-emerald-100 hover:text-emerald-700",
                  isActive
                    ? "bg-emerald-100 text-emerald-700 shadow-sm"
                    : "text-muted-foreground"
                )}
              >
                <item.icon className="h-5 w-5 text-current" />
                {item.title}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto p-6 pt-4 border-t">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-xl font-semibold"
          onClick={logout}
        >
          <LogOut className="h-5 w-5" />
          Logout
        </Button>
      </div>
    </div>
  );
});

const MobileNav = memo(function MobileNav() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle navigation menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="p-0 w-[260px]">
        <Sidebar className="border-none h-full" />
      </SheetContent>
    </Sheet>
  );
});

export { Sidebar, MobileNav };
