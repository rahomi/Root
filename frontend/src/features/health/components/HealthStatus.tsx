"use client";

import { useHealth } from "@/features/health/hooks/useHealth";

export function HealthStatus() {
  const { data, isLoading, error } = useHealth();

  if (isLoading) {
    return <p>Checking API status...</p>;
  }

  if (error) {
    return <p>API error: {error}</p>;
  }

  if (!data) {
    return <p>No health data available.</p>;
  }

  return (
    <section>
      <h2>Backend Health</h2>
      <p>Status: {data.status}</p>
      <p>Probe Target: {data.target}</p>
      <p>Timestamp: {data.timestamp}</p>
    </section>
  );
}
