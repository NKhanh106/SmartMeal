"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AlertCircle, Loader2, Plus, Trash2, UtensilsCrossed } from "lucide-react";
import { mealService } from "@/services/meal.service";
import { useToast } from "@/hooks/use-toast";
import type { MealLogSummaryResponse } from "@/lib/types/api";

function MealTypeBadge({ mealType }: { mealType: string }) {
  const map: Record<string, { label: string; className: string }> = {
    bua_sang: { label: "Breakfast", className: "bg-orange-100 text-orange-700 hover:bg-orange-100" },
    bua_trua: { label: "Lunch", className: "bg-blue-100 text-blue-700 hover:bg-blue-100" },
    bua_toi: { label: "Dinner", className: "bg-indigo-100 text-indigo-700 hover:bg-indigo-100" },
    an_vat: { label: "Snack", className: "bg-purple-100 text-purple-700 hover:bg-purple-100" },
    khac: { label: "Other", className: "bg-slate-100 text-slate-700 hover:bg-slate-100" },
  };
  const config = map[mealType] ?? { label: mealType, className: "bg-slate-100 text-slate-700 hover:bg-slate-100" };
  return (
    <Badge variant="secondary" className={config.className}>
      {config.label}
    </Badge>
  );
}

function formatDate(isoString: string) {
  const date = new Date(isoString);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  return (
    <ErrorBoundary>
      <HistoryPageInner />
    </ErrorBoundary>
  );
}

function HistoryPageInner() {
  const [logs, setLogs] = useState<MealLogSummaryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await mealService.getMyMealLogs({ limit: 100 });
      setLogs(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load meal history";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleDelete = useCallback(async (logId: string) => {
    setDeletingId(logId);
    try {
      await mealService.deleteMealLog(logId);
      setLogs((prev) => prev.filter((l) => l.id !== logId));
      toast({ title: "Meal deleted successfully." });
    } catch (e) {
      toast({
        title: "Failed to delete meal.",
        description: e instanceof Error ? e.message : "Please try again.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
      setDeleteConfirmId(null);
    }
  }, [toast]);

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
          <h1 className="text-3xl font-bold">Meal History</h1>
          <p className="text-muted-foreground">Your logged meals over time.</p>
        </div>
        </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm">{error}</p>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={fetchLogs}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <Card>
          <CardContent className="p-6 space-y-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-20 rounded-full" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!loading && !error && logs.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 py-16 text-center">
          <UtensilsCrossed className="mb-3 h-10 w-10 text-slate-300" />
          <h3 className="font-semibold text-slate-600">No meals logged yet</h3>
          <p className="mt-1 text-sm text-slate-400">
            Start logging your meals to see your history here
          </p>
          <Button className="mt-4 gap-2" onClick={() => window.location.href = "/upload"}>
            <Plus className="h-4 w-4" />
            Log your first meal
          </Button>
        </div>
      )}

      {/* Table */}
      {!loading && logs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Logged Meals ({logs.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Calories</TableHead>
                  <TableHead className="text-right">Protein (g)</TableHead>
                  <TableHead className="text-right">Carbs (g)</TableHead>
                  <TableHead className="text-right">Fat (g)</TableHead>
                  <TableHead className="w-[50px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-medium">
                      {formatDate(log.meal_time)}
                    </TableCell>
                    <TableCell>
                      <MealTypeBadge mealType={log.meal_type} />
                    </TableCell>
                    <TableCell>
                      <span className="font-semibold">{Math.round(log.total_calories).toLocaleString()}</span>
                      <span className="ml-1 text-xs text-slate-400">kcal</span>
                    </TableCell>
                    <TableCell className="text-right">{Math.round(log.total_protein_g)}</TableCell>
                    <TableCell className="text-right">{Math.round(log.total_carb_g)}</TableCell>
                    <TableCell className="text-right">{Math.round(log.total_fat_g)}</TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-slate-400 hover:text-red-500"
                        disabled={deletingId === log.id}
                        onClick={() => setDeleteConfirmId(log.id)}
                        title="Delete meal log"
                      >
                        {deletingId === log.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      </div>
      {/* ── Delete Confirmation Dialog ──────────────────────────────────────── */}
      <AlertDialog open={deleteConfirmId !== null} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete meal log?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The meal will be permanently removed from your history.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

