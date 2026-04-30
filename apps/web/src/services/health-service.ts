import { api } from "@/lib/api-client";

export type HealthResponse = {
  status?: string;
  message?: string;
};

export async function getHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>("/health");
}
