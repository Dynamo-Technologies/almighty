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

function base64UrlDecode(input: string): string {
  const padded = input.padEnd(input.length + ((4 - (input.length % 4)) % 4), "=");
  const std = padded.replace(/-/g, "+").replace(/_/g, "/");
  return atob(std);
}

export function decodeJwt(token: string): JwtClaims | null {
  try {
    const [, payloadB64] = token.split(".");
    if (!payloadB64) return null;
    const payload = JSON.parse(base64UrlDecode(payloadB64)) as Partial<JwtClaims>;
    if (typeof payload.tenant_id !== "string") return null;
    if (
      payload.cell_role !== "white" &&
      payload.cell_role !== "blue" &&
      payload.cell_role !== "red" &&
      payload.cell_role !== "observer"
    ) {
      return null;
    }
    return payload as JwtClaims;
  } catch {
    return null;
  }
}

// Resolves a token from (in priority order): ?jwt= query param (also persists
// to localStorage), then localStorage. The query-param flow is a hackathon
// convenience for demos; real auth lands in a future ticket.
function resolveToken(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("jwt");
  if (fromQuery) {
    window.localStorage.setItem(STORAGE_KEY, fromQuery);
    return fromQuery;
  }
  return window.localStorage.getItem(STORAGE_KEY);
}

export function useJwtClaims(): JwtClaims | null {
  const [claims, setClaims] = useState<JwtClaims | null>(() => {
    const tok = resolveToken();
    return tok ? decodeJwt(tok) : null;
  });

  useEffect(() => {
    const onStorage = () => {
      const tok = resolveToken();
      setClaims(tok ? decodeJwt(tok) : null);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return claims;
}

export function getStoredToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY);
}
