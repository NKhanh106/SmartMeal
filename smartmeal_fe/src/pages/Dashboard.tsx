/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from 'motion/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { 
  Plus, 
  ArrowUpRight, 
  Flame, 
  Target, 
  Utensils, 
  Clock 
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { Progress } from '@/components/ui/progress';

const macroData = [
  { name: 'Protein', value: 35, color: '#3b82f6' },
  { name: 'Carbs', value: 45, color: '#10b981' },
  { name: 'Fat', value: 20, color: '#f59e0b' },
];

const calorieHistory = [
  { day: 'Mon', calories: 2100 },
  { day: 'Tue', calories: 2300 },
  { day: 'Wed', calories: 1950 },
  { day: 'Thu', calories: 2500 },
  { day: 'Fri', calories: 2200 },
  { day: 'Sat', calories: 2100 },
  { day: 'Sun', calories: 2200 },
];

export default function Dashboard() {
  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Today's Overview</h1>
          <p className="text-muted-foreground">Keep up the good work, Nguyễn! You're 80% to your goal.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" className="gap-2">
            <Plus className="h-4 w-4" />
            Add Meal
          </Button>
          <Button size="sm" variant="outline" className="gap-2">
            <Clock className="h-4 w-4" />
            History
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          { title: 'Calories', value: '1,840', sub: '/ 2,200', icon: Flame, color: 'text-orange-500', progress: 84, trend: '550 kcal left' },
          { title: 'Protein', value: '110g', sub: '/ 150g', icon: Target, color: 'text-blue-500', progress: 73, trend: '74% of goal' },
          { title: 'Carbs', value: '180g', sub: '/ 250g', icon: Utensils, color: 'text-emerald-500', progress: 72, trend: 'Near limit' },
          { title: 'Fat', value: '45g', sub: '/ 70g', icon: Utensils, color: 'text-amber-500', progress: 64, trend: 'Well balanced' },
        ].map((stat, i) => (
          <motion.div
            key={stat.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className="border-slate-200/60 shadow-sm hover:shadow-md transition-shadow rounded-2xl overflow-hidden">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="p-2 rounded-xl bg-slate-50">
                    <stat.icon className={cn("h-5 w-5", stat.color)} />
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{stat.title}</span>
                </div>
                <div className="space-y-1">
                  <div className="flex items-baseline gap-1">
                    <h3 className="text-2xl font-bold text-slate-900">{stat.value}</h3>
                    <p className="text-sm text-slate-400 font-medium">{stat.sub}</p>
                  </div>
                  <p className={cn("text-xs font-semibold", 
                    stat.trend === 'Near limit' ? 'text-amber-500' : 'text-emerald-500'
                  )}>{stat.trend}</p>
                </div>
                <Progress value={stat.progress} className="mt-4 h-1.5 bg-slate-100" />
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
        <Card className="lg:col-span-4 border-slate-200/60 shadow-sm rounded-2xl">
          <CardContent className="p-8">
            <div className="flex items-center justify-between mb-8">
              <h3 className="text-lg font-bold text-slate-900">Weekly Calorie Intake</h3>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Last 7 Days</span>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={calorieHistory}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                  <XAxis 
                    dataKey="day" 
                    axisLine={false} 
                    tickLine={false} 
                    fontSize={12} 
                    tick={{ fill: '#94A3B8', fontWeight: 600 }}
                    dy={10}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    fontSize={12} 
                    tick={{ fill: '#94A3B8', fontWeight: 600 }}
                  />
                  <Tooltip 
                    cursor={{ fill: '#F8FAFC', radius: 8 }}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  />
                  <Bar dataKey="calories" fill="#10B981" radius={[6, 6, 0, 0]} barSize={36} opacity={0.9} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-3 border-slate-200/60 shadow-sm rounded-2xl">
          <CardContent className="p-8">
            <h3 className="text-lg font-bold text-slate-900 mb-8">Macro Distribution</h3>
            <div className="h-[260px] w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={macroData}
                    innerRadius={70}
                    outerRadius={90}
                    paddingAngle={8}
                    dataKey="value"
                    stroke="none"
                  >
                    {macroData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400">Total</span>
                <span className="text-3xl font-extrabold text-slate-900">1,840</span>
                <span className="text-[10px] font-bold text-emerald-500">kcal</span>
              </div>
            </div>
            <div className="mt-8 space-y-3">
              {macroData.map((macro) => (
                <div key={macro.name} className="flex items-center justify-between p-3 rounded-xl bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-2 rounded-full" style={{ backgroundColor: macro.color }} />
                    <span className="text-sm font-bold text-slate-600">{macro.name}</span>
                  </div>
                  <span className="text-sm font-extrabold text-slate-900">{macro.value}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}

// Helper to use cn in pages
import { cn } from '@/lib/utils';
