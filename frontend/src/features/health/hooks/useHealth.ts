"use client";

import { useEffect, useState } from "react";
import type { Health } from "@/features/health/types";
import { getHealth } from "@/features/health/services/getHealth";

type UseHealthResult = {
  data: Health | null;
  isLoading: boolean;
  error: string | null;
};

export function useHealth(): UseHealthResult {
  const [data, setData] = useState<Health | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    async function run() {
      try {
        const result = await getHealth();
        if (isActive) {
          setData(result);
        }
      } catch (err) {
        if (isActive) {
          const message =
            err instanceof Error ? err.message : "Unknown error occurred";
          setError(message);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }
    run();
    return () => {
      isActive = false;
    };
  }, []);

  return { data, isLoading, error };
}
