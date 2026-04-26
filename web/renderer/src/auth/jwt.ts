// Lightweight client-side JWT decode. NO verification — the server is the
// source of truth for auth; the renderer reads claims only to gate which
// route to show / which cell-role console to render. JWT integrity is
// re-verified on every API call by the control-plane and websocket service.

import { useEffect, useState } from "react";

export type CellRole = "white" | "blue" | "red" | "observer";

export interface JwtClaims {
  tenant_id: string;
  cell_role: CellRole;
  sub?: string;
  exp?: number;
  iat?: number;
}

const STORAGE_KEY = "almighty.jwt";
const CELL_ROLES: readonly CellRole[] = ["white", "blue", "red", "observer"];

function base64UrlDecode(input: string): string {
  const padded = input.padEnd(input.length + ((4 - (input.length % 4)) % 4), "=");
  const std = padded.replace(/-/g, "+").replace(/_/g, "/");
  return atob(std);
}

function base64UrlEncode(s: string): string {
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function decodeJwt(token: string): JwtClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payloadB64 = parts[1];
    if (!payloadB64) return null;
    const payload = JSON.parse(base64UrlDecode(payloadB64)) as Partial<JwtClaims>;
    if (typeof payload.tenant_id !== "string") return null;
    if (!CELL_ROLES.includes(payload.cell_role as CellRole)) return null;
    return payload as JwtClaims;
  } catch {
    return null;
  }
}

/**
 * Mints an unsigned (`alg: "none"`) JWT for client-side dev use. The server
 * will reject these — they're only good for the renderer's own route gating
 * until a real auth flow lands.
 */
export function mintDevJwt(claims: JwtClaims): string {
  const header = base64UrlEncode(JSON.stringify({ alg: "none", typ: "JWT" }));
  const payload = base64UrlEncode(JSON.stringify(claims));
  return `${header}.${payload}.`;
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, token);
  window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY, newValue: token }));
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY, newValue: null }));
}

export function getStoredToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY);
}

/**
 * Reads the JWT from localStorage only. v1 deliberately removed the
 * `?jwt=<token>` URL flow — that was a phishing-shaped vector (any link
 * could silently overwrite the stored token with attacker claims). Use
 * the DevTokenForm to set a token instead.
 */
export function useJwtClaims(): JwtClaims | null {
  const [claims, setClaims] = useState<JwtClaims | null>(() => {
    const tok = getStoredToken();
    return tok ? decodeJwt(tok) : null;
  });

  useEffect(() => {
    const refresh = () => {
      const tok = getStoredToken();
      setClaims(tok ? decodeJwt(tok) : null);
    };
    window.addEventListener("storage", refresh);
    return () => window.removeEventListener("storage", refresh);
  }, []);

  return claims;
}
