/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Bell, Search, User as UserIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { MobileNav } from './Sidebar';

export function Header() {
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
        <Button variant="ghost" size="icon" className="relative text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 rounded-xl transition-all">
          <Bell className="h-5 w-5" />
          <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-emerald-500 border-2 border-white" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-10 w-10 rounded-full p-0 border-2 border-white shadow-sm ring-1 ring-slate-100 overflow-hidden hover:ring-emerald-200 transition-all">
              <Avatar className="h-full w-full">
                <AvatarImage src="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=150&h=150" alt="User" />
                <AvatarFallback>JD</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56 mt-2 rounded-xl border-slate-100 shadow-xl shadow-slate-200/50" align="end" forceMount>
            <DropdownMenuLabel className="font-normal p-4">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-bold leading-none text-slate-900">Nguyễn Văn A</p>
                <p className="text-xs leading-none text-slate-500">nguyenvana@example.com</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-slate-50" />
            <div className="p-1">
              <DropdownMenuItem className="rounded-lg cursor-pointer">Profile</DropdownMenuItem>
              <DropdownMenuItem className="rounded-lg cursor-pointer">Settings</DropdownMenuItem>
              <DropdownMenuItem className="rounded-lg cursor-pointer">Billing</DropdownMenuItem>
            </div>
            <DropdownMenuSeparator className="bg-slate-50" />
            <div className="p-1">
              <DropdownMenuItem className="text-red-500 rounded-lg cursor-pointer focus:bg-red-50 focus:text-red-600">Log out</DropdownMenuItem>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
