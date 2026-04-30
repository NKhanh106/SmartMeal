/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function DashboardLayout() {
  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans selection:bg-emerald-100 selection:text-emerald-900">
      <aside className="hidden w-[260px] md:block flex-shrink-0">
        <Sidebar className="fixed w-[260px]" />
      </aside>
      <div className="flex flex-col flex-grow min-w-0">
        <Header />
        <main className="flex-grow p-4 md:p-8 lg:p-10">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
