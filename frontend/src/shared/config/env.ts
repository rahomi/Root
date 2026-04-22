function getPublicApiBaseUrl(): string {
  // Next.js only inlines NEXT_PUBLIC_* vars when accessed directly.
  const value = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!value) {
    throw new Error(
      "Missing required environment variable: NEXT_PUBLIC_API_BASE_URL"
    );
  }
  return value;
}

function getPublicApiHealthPath(): string {
  const value = process.env.NEXT_PUBLIC_API_HEALTH_PATH;
  if (!value) {
    return "/admin/login/";
  }
  return value.startsWith("/") ? value : `/${value}`;
}

export const env = {
  apiBaseUrl: getPublicApiBaseUrl(),
  apiHealthPath: getPublicApiHealthPath()
};
