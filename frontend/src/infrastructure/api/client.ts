import { env } from "@/shared/config/env";

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function getApiErrorMessage(status: number, payload: unknown): string {
  if (
    payload &&
    typeof payload === "object" &&
    "message" in payload &&
    typeof (payload as { message?: unknown }).message === "string"
  ) {
    return (payload as { message: string }).message;
  }

  return status > 0 ? `API request failed with status ${status}` : "API request failed";
}

type RequestOptions = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
};

async function requestJson<T>(
  url: string,
  options: RequestOptions = {}
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers ?? {})
      },
      cache: "no-store"
    });
  } catch {
    throw new ApiError(
      `Network error while calling ${url}. Check backend availability.`,
      0,
      null
    );
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new ApiError(
      getApiErrorMessage(response.status, payload),
      response.status,
      payload
    );
  }

  return payload as T;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  return requestJson<T>(`${env.apiBaseUrl}${path}`, options);
}

export async function internalApiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  return requestJson<T>(path, options);
}
