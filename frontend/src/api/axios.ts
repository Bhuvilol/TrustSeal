import axios from 'axios';
import { clearStoredToken, getStoredToken, isTokenExpired } from '@/utils/token';

const prodApiBase = 'https://trust-seal-1.onrender.com';
const fallbackApiBase = import.meta.env.DEV ? 'http://localhost:8000' : prodApiBase;
const fallbackTimeoutMs = 20_000;

export const apiClient = axios.create({
  baseURL: String(import.meta.env.VITE_API_BASE_URL || fallbackApiBase).trim(),
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS || fallbackTimeoutMs),
});

type RetryConfig = {
  __localPortFailoverTried?: boolean;
  baseURL?: string;
};

function getAlternateLocalBaseURL(baseURL: string | undefined): string | null {
  if (!import.meta.env.DEV || !baseURL) {
    return null;
  }

  try {
    const parsed = new URL(baseURL);
    const isLocalHost = parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
    if (!isLocalHost) {
      return null;
    }

    if (parsed.port === '8000') {
      parsed.port = '8001';
      return parsed.toString().replace(/\/$/, '');
    }

    if (parsed.port === '8001') {
      parsed.port = '8000';
      return parsed.toString().replace(/\/$/, '');
    }

    return null;
  } catch {
    return null;
  }
}

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (!token) {
    return config;
  }

  if (isTokenExpired(token)) {
    clearStoredToken();
    window.dispatchEvent(new CustomEvent('trustseal:unauthorized'));
    return config;
  }

  config.headers = config.headers ?? {};
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = (error?.config || {}) as RetryConfig & Record<string, unknown>;
    const shouldTryLocalFailover =
      !error?.response &&
      !config.__localPortFailoverTried &&
      (error?.code === 'ERR_NETWORK' || error?.code === 'ECONNABORTED');

    if (shouldTryLocalFailover) {
      const currentBase = String(config.baseURL || apiClient.defaults.baseURL || '');
      const alternateBase = getAlternateLocalBaseURL(currentBase);
      if (alternateBase) {
        config.__localPortFailoverTried = true;
        config.baseURL = alternateBase;
        return apiClient.request(config);
      }
    }

    if (error.response?.status === 401) {
      clearStoredToken();
      window.dispatchEvent(new CustomEvent('trustseal:unauthorized'));
    }

    if (error.response?.status === 403) {
      const forbiddenDetail = error?.response?.data?.detail;
      const message =
        typeof forbiddenDetail === 'string' && forbiddenDetail.trim().length > 0
          ? forbiddenDetail
          : 'Insufficient permissions for this operation.';
      window.dispatchEvent(new CustomEvent('trustseal:forbidden', { detail: message }));
    }

    return Promise.reject(error);
  },
);
