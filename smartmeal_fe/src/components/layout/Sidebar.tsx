/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
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
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';

interface NavItem {
  title: string;
  href: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { title: 'Health Profile', href: '/profile', icon: User },
  { title: 'Nutrition Goals', href: '/goals', icon: Target },
  { title: 'Upload Meal', href: '/upload', icon: Camera },
  { title: 'Meal History', href: '/history', icon: History },
  { title: 'Analytics', href: '/analytics', icon: BarChart2 },
  { title: 'Recommendations', href: '/recommendations', icon: Zap },
  { title: 'Workout Plan', href: '/workout', icon: Dumbbell },
];

export function Sidebar({ className }: { className?: string }) {
  return (
    <div className={cn("pb-12 h-screen border-r bg-card flex flex-col", className)}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-10">
          <div className="h-8 w-8 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
            S
          </div>
          <span className="font-extrabold text-xl tracking-tight">SmartMeal</span>
        </div>
        
        <nav className="space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) => 
                cn(
                  "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-all hover:bg-accent hover:text-accent-foreground",
                  isActive ? "bg-accent text-accent-foreground shadow-sm" : "text-slate-500"
                )
              }
            >
              <item.icon className={cn("h-5 w-5", "text-current")} />
              {item.title}
            </NavLink>
          ))}
        </nav>
      </div>
      
      <div className="mt-auto p-6 pt-4 border-t border-slate-50">
        <Button variant="ghost" className="w-full justify-start gap-3 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-xl font-semibold">
          <LogOut className="h-5 w-5" />
          Logout
        </Button>
      </div>
    </div>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" className="md:hidden">
          <Menu className="h-6 w-6" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="p-0 w-[240px]">
        <Sidebar className="border-none" />
      </SheetContent>
    </Sheet>
  );
}
