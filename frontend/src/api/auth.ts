import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { RegisterPayload, RegisterResponse, TokenResponse, User } from '@/types';

const AUTH_BASE = `${API_PREFIX}/auth`;

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  const { data } = await apiClient.post<RegisterResponse>(`${AUTH_BASE}/register`, payload);
  return data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.append('username', email);
  body.append('password', password);

  const { data } = await apiClient.post<TokenResponse>(`${AUTH_BASE}/login`, body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>(`${AUTH_BASE}/me`);
  return data;
}

