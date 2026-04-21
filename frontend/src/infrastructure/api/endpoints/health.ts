import { internalApiRequest } from "@/infrastructure/api/client";

export type HealthResponseDto = {
  status: string;
  target: string;
  timestamp: string;
};

export function getHealthDto() {
  return internalApiRequest<HealthResponseDto>("/api/health");
}
