import { env } from "@/shared/config/env";

export async function GET() {
  try {
    const response = await fetch(`${env.apiBaseUrl}${env.apiHealthPath}`, {
      cache: "no-store",
      redirect: "manual"
    });

    const isReachable = response.status >= 200 && response.status < 400;
    if (isReachable) {
      return Response.json({
        status: "up",
        target: env.apiHealthPath,
        timestamp: new Date().toISOString()
      });
    }

    return Response.json(
      {
        status: "down",
        target: env.apiHealthPath,
        timestamp: new Date().toISOString(),
        message: "Backend probe returned non-success status.",
        statusCode: response.status
      },
      { status: 503 }
    );
  } catch {
    return Response.json(
      {
        status: "down",
        target: env.apiHealthPath,
        timestamp: new Date().toISOString(),
        message:
          "Backend is unreachable. Make sure API server is running, NEXT_PUBLIC_API_BASE_URL is correct, and probe path exists."
      },
      { status: 503 }
    );
  }
}
