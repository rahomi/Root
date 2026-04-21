import { getHealthDto } from "@/infrastructure/api/endpoints/health";
import type { Health } from "@/features/health/types";

export async function getHealth(): Promise<Health> {
  const dto = await getHealthDto();
  return {
    status: dto.status,
    target: dto.target,
    timestamp: dto.timestamp
  };
}
