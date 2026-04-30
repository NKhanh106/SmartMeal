/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { NutritionGoal } from '@/types';
import { getNutritionGoals } from '@/services/mockService';
import { Target, Flame, Utensils, Droplet } from 'lucide-react';

export default function Goals() {
  const [goals, setGoals] = useState<NutritionGoal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNutritionGoals().then(data => {
      setGoals(data);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Nutrition Goals</h1>
        <Button variant="outline" size="sm">Calculate BMI</Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Flame className="h-5 w-5 text-orange-500" />
              Daily Caloric Target
            </CardTitle>
            <CardDescription>Adjust your daily energy intake based on your goals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="calories">Energy (kcal)</Label>
              <Input id="calories" type="number" defaultValue={goals?.calories} />
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold p-2">Weight Loss</Button>
              <Button size="sm" variant="ghost" className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold p-2">Maintenance</Button>
              <Button size="sm" variant="ghost" className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold p-2">Muscle Gain</Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Droplet className="h-5 w-5 text-blue-500" />
              Hydration Goal
            </CardTitle>
            <CardDescription>Minimum daily water intake recommended.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="water">Water (Liters)</Label>
              <Input id="water" type="number" step="0.1" defaultValue={goals?.water} />
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Utensils className="h-5 w-5 text-primary" />
              Macronutrient Targets
            </CardTitle>
            <CardDescription>Customize the ratio of Protein, Carbs, and Fats.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="protein">Protein (g)</Label>
                <Input id="protein" type="number" defaultValue={goals?.protein} />
                <p className="text-xs text-muted-foreground">About {(goals?.protein || 0) * 4} kcal</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="carbs">Carbohydrates (g)</Label>
                <Input id="carbs" type="number" defaultValue={goals?.carbs} />
                <p className="text-xs text-muted-foreground">About {(goals?.carbs || 0) * 4} kcal</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fat">Fats (g)</Label>
                <Input id="fat" type="number" defaultValue={goals?.fat} />
                <p className="text-xs text-muted-foreground">About {(goals?.fat || 0) * 9} kcal</p>
              </div>
            </div>
            <div className="mt-8">
              <Button className="w-full">Update Goals</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
