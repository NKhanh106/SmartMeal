import { api } from "@/lib/api-client";

/**
 * Health check service.
 *
 * TODO: Wire this into the Dashboard health summary section.
 * Function is ready but not yet connected to any UI component.
 * See: src/app/(dashboard)/dashboard/page.tsx
 *
 * Usage:
 *   const health = await getHealth();
 *   console.log(health.status); // "ok"
 */
export type HealthResponse = {
  status?: string;
  message?: string;
};

export async function getHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>("/health");
}
