/** Server-side only: where the FastAPI backend lives (inside Docker: http://backend:8000). */
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

export const COOKIE_TOKEN = "ff_token";
export const COOKIE_ORG = "ff_org";
export const COOKIE_LANG = "lang";

/** Set COOKIE_SECURE=true when the site is served over HTTPS. */
export const COOKIE_SECURE = process.env.COOKIE_SECURE === "true";
