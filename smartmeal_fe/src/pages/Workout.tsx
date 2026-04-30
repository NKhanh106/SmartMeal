/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getWorkoutPlan } from '@/services/mockService';
import { WorkoutPlan } from '@/types';
import { 
  Play, 
  CheckCircle2, 
  Dumbbell, 
  Timer, 
  Zap as BurnIcon,
  ChevronRight
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';

export default function Workout() {
  const [plans, setPlans] = useState<WorkoutPlan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getWorkoutPlan().then(d => {
      setPlans(d);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Personalized Workout</h1>
          <p className="text-muted-foreground">Tailored routines based on your goals and energy levels.</p>
        </div>
        <div className="flex bg-accent/50 rounded-full p-1 border">
          <Button variant="ghost" size="sm" className="rounded-full bg-white shadow-sm">Cardio</Button>
          <Button variant="ghost" size="sm" className="rounded-full font-bold">Strength</Button>
          <Button variant="ghost" size="sm" className="rounded-full font-bold">Yoga</Button>
        </div>
      </div>

      <div className="grid gap-6">
        {plans.map((plan, i) => (
          <Card key={plan.id} className="overflow-hidden">
            <div className="bg-primary/5 px-6 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-primary">{plan.day}</h3>
                <p className="text-sm font-medium text-primary/70">{plan.type}</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-xs text-muted-foreground uppercase font-bold">Est. Burn</p>
                  <p className="text-lg font-bold">~{plan.totalEstimatedCalories} kcal</p>
                </div>
                <Button size="icon" className="rounded-full shadow-lg h-12 w-12">
                  <Play className="h-6 w-6 ml-1" />
                </Button>
              </div>
            </div>
            <CardContent className="p-0">
              <div className="divide-y">
                {plan.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between p-6 hover:bg-accent/10 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-xl bg-accent/50 flex items-center justify-center">
                        <Dumbbell className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <h4 className="font-bold">{item.name}</h4>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                            <RefreshCw className="h-3 w-3" />
                            {item.sets} Sets
                          </span>
                          <span className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                            <BurnIcon className="h-3 w-3 text-orange-500" />
                            {item.reps} Reps
                          </span>
                        </div>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon">
                      <ChevronRight className="h-5 w-5" />
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle>Daily Progress</CardTitle>
          <CardDescription>You've completed 2/4 sessions this week!</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Progress value={50} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground font-semibold">
              <span>Goal: 4 Sessions</span>
              <span>2 Remaining</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

import { RefreshCw } from 'lucide-react';
