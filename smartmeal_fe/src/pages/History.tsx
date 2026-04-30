/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { getMealLogs } from '@/services/mockService';
import { MealLog } from '@/types';

export default function History() {
  const [logs, setLogs] = useState<MealLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMealLogs().then(data => {
      setLogs(data);
      setLoading(false);
    });
  }, []);

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'breakfast': return 'bg-orange-100 text-orange-700 hover:bg-orange-100';
      case 'lunch': return 'bg-blue-100 text-blue-700 hover:bg-blue-100';
      case 'dinner': return 'bg-indigo-100 text-indigo-700 hover:bg-indigo-100';
      default: return 'bg-slate-100 text-slate-700 hover:bg-slate-100';
    }
  };

  const formatLocally = (date: Date) => {
    return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Meal History</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>Logged Meals</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Meal Items</TableHead>
                <TableHead className="text-right">Calories</TableHead>
                <TableHead className="text-right">Protein (g)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="font-medium">
                    {formatLocally(new Date(log.timestamp))}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={getTypeColor(log.type)}>
                      {log.type.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs text-muted-foreground">
                      {log.items.map(item => item.name).join(', ')}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">{log.totalCalories}</TableCell>
                  <TableCell className="text-right">{log.totalProtein}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

