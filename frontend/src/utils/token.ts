import { ACCESS_TOKEN_KEY } from '@/utils/constants';
const ACCESS_ROLE_KEY = 'trustseal_role';
const ACCESS_USER_ID_KEY = 'trustseal_user_id';

interface JwtPayload {
  exp?: number;
  sub?: string;
  [key: string]: unknown;
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return atob(padded);
}

export function getStoredToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(ACCESS_ROLE_KEY);
  localStorage.removeItem(ACCESS_USER_ID_KEY);
}

export function setStoredRole(role: string): void {
  localStorage.setItem(ACCESS_ROLE_KEY, role);
}

export function getStoredRole(): string | null {
  return localStorage.getItem(ACCESS_ROLE_KEY);
}

export function setStoredUserId(id: string): void {
  localStorage.setItem(ACCESS_USER_ID_KEY, id);
}

export function getStoredUserId(): string | null {
  return localStorage.getItem(ACCESS_USER_ID_KEY);
}

export function parseJwtPayload(token: string): JwtPayload | null {
  try {
    const segments = token.split('.');
    if (segments.length < 2) {
      return null;
    }
    const decoded = decodeBase64Url(segments[1]);
    return JSON.parse(decoded) as JwtPayload;
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string, graceWindowSeconds = 15): boolean {
  const payload = parseJwtPayload(token);
  if (!payload?.exp) {
    return true;
  }

  const currentEpoch = Date.now() / 1000;
  return currentEpoch >= payload.exp - graceWindowSeconds;
}

