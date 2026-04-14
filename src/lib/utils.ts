import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getApiBaseUrl() {
  const rawUrl = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api").trim();
  const normalizedUrl = rawUrl.replace(/\/+$/, "");
  return normalizedUrl.endsWith("/api") ? normalizedUrl : `${normalizedUrl}/api`;
}
