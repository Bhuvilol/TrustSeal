import type { AxiosError } from 'axios';
import type { ApiErrorPayload } from '@/types';

export function getHttpStatus(error: unknown): number | undefined {
  const axiosError = error as AxiosError<ApiErrorPayload> | undefined;
  return axiosError?.response?.status;
}

export function getErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  const axiosError = error as AxiosError<ApiErrorPayload> | undefined;
  const detail = axiosError?.response?.data?.detail;
  const message = axiosError?.response?.data?.message;
  const axiosMessage = axiosError?.message;

  if (axiosError?.code === 'ECONNABORTED') {
    return 'Request timed out. Backend is slow or unreachable. Please retry.';
  }

  if (axiosError?.code === 'ERR_NETWORK') {
    return 'Unable to reach backend API. Start backend server and verify API base URL/port.';
  }

  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }

  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }

  if (typeof axiosMessage === 'string' && axiosMessage.trim().length > 0) {
    return axiosMessage;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
}

