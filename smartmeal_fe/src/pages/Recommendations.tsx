/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  getDailyRecommendation 
} from '@/services/mockService';
import { DailyRecommendation } from '@/types';
import { 
  Coffee, 
  Sun, 
  Moon, 
  Cookie, 
  Lightbulb, 
  RefreshCw 
} from 'lucide-react';

export default function Recommendations() {
  const [data, setData] = useState<DailyRecommendation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDailyRecommendation().then(d => {
      setData(d);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Daily Recommendations</h1>
          <p className="text-muted-foreground">AI-generated meal plans and health tips just for you.</p>
        </div>
        <Button variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Regenerate
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[
          { title: 'Breakfast', menu: data?.breakfast, icon: Coffee, color: 'text-orange-500' },
          { title: 'Lunch', menu: data?.lunch, icon: Sun, color: 'text-yellow-500' },
          { title: 'Dinner', menu: data?.dinner, icon: Moon, color: 'text-indigo-500' },
        ].map((meal) => (
          <Card key={meal.title} className="relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <meal.icon className="h-12 w-12" />
            </div>
            <CardHeader>
              <div className="flex items-center gap-2 mb-2">
                <meal.icon className={cn("h-5 w-5", meal.color)} />
                <Badge variant="outline">{meal.title}</Badge>
              </div>
              <CardTitle className="text-xl">{meal.menu}</CardTitle>
            </CardHeader>
            <CardContent>
              <Button variant="link" className="p-0 h-auto text-primary">View Full Recipe →</Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cookie className="h-5 w-5 text-amber-600" />
              Healthy Snack Ideas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {data?.snacks.map((snack, i) => (
                <li key={i} className="flex items-center gap-3 p-3 bg-accent/30 rounded-lg">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                  <span className="text-sm font-medium">{snack}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="bg-primary text-primary-foreground">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5" />
              AI Health Tips
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-4">
              {data?.tips.map((tip, i) => (
                <li key={i} className="flex gap-3">
                  <span className="font-bold text-primary-foreground/50">{i + 1}.</span>
                  <p className="text-sm border-l-2 border-primary-foreground/20 pl-3 leading-relaxed">
                    {tip}
                  </p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

import { cn } from '@/lib/utils';
