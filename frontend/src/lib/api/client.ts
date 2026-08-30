import axios from "axios";
import { API_BASE_URL } from "@/lib/constants";

/**
 * Shared Axios instance.
 * - Base URL comes from NEXT_PUBLIC_API_URL (defaults to the local backend),
 *   and can be overridden at runtime from Settings → API Configuration
 *   (stored under `bta-api-url` in localStorage).
 * - On error we attach a normalized `message` so UI error states stay consistent.
 */

/** The localStorage key Settings → API Configuration writes to. */
export const API_URL_STORAGE_KEY = "bta-api-url";

/** Resolve the effective API base URL (runtime override wins). */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(API_URL_STORAGE_KEY);
    if (saved) return saved.replace(/\/$/, "");
  }
  return API_BASE_URL;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// Apply the runtime API URL override (if any) on every request.
apiClient.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let message = "Network error — is the backend running?";
    if (error.response) {
      const detail = error.response.data?.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) {
        message = detail.map((d) => d.msg).join("; ");
      } else if (error.response.data?.message) {
        message = error.response.data.message;
      } else {
        message = `Request failed (${error.response.status})`;
      }
    } else if (error.code === "ECONNABORTED") {
      message = "Request timed out";
    }
    error.userMessage = message;
    return Promise.reject(error);
  }
);

/** Extracts a human readable message from any error. */
export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err) && err.userMessage) return err.userMessage;
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred";
}

declare module "axios" {
  export interface AxiosError {
    userMessage?: string;
  }
}
