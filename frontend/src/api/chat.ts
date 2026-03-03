import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { ChatResponse } from '@/types';

interface ChatRequestBody {
  message: string;
  tenant_id?: string;
  device_id?: string;
  session_id?: string;
  top_k?: number;
}

interface SendAdminChatOptions {
  tenantId?: string;
  deviceId?: string;
  sessionId?: string;
  topK?: number;
}

export async function sendAdminChat(message: string, options?: SendAdminChatOptions): Promise<ChatResponse> {
  const payload: ChatRequestBody = { message };

  const tenantId = options?.tenantId?.trim();
  if (tenantId) {
    payload.tenant_id = tenantId;
  }

  const deviceId = options?.deviceId?.trim();
  if (deviceId) {
    payload.device_id = deviceId;
  }

  const sessionId = options?.sessionId?.trim();
  if (sessionId) {
    payload.session_id = sessionId;
  }

  if (typeof options?.topK === 'number' && options.topK > 0) {
    payload.top_k = options.topK;
  }

  const { data } = await apiClient.post<ChatResponse>(`${API_PREFIX}/chat`, payload);
  return data;
}
