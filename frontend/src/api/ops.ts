import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type {
  DeadLetterReprocessResponse,
  PipelineStatusResponse,
  ReconcileResponse,
  RetryAnchorResponse,
  RetryCustodyGateResponse,
  RetryIpfsResponse,
  WorkersStatusResponse,
} from '@/types';

export async function getPipelineStatus(shipmentId?: string): Promise<PipelineStatusResponse> {
  const { data } = await apiClient.get<PipelineStatusResponse>(`${API_PREFIX}/ops/pipeline-status`, {
    params: shipmentId ? { shipment_id: shipmentId } : undefined,
  });
  return data;
}

export async function retryAnchor(bundleId: string): Promise<RetryAnchorResponse> {
  const { data } = await apiClient.post<RetryAnchorResponse>(`${API_PREFIX}/ops/retry/anchor`, null, {
    params: { bundle_id: bundleId },
  });
  return data;
}

export async function retryIpfs(bundleId: string): Promise<RetryIpfsResponse> {
  const { data } = await apiClient.post<RetryIpfsResponse>(`${API_PREFIX}/ops/retry/ipfs`, null, {
    params: { bundle_id: bundleId },
  });
  return data;
}

export async function retryCustodyGate(bundleId: string): Promise<RetryCustodyGateResponse> {
  const { data } = await apiClient.post<RetryCustodyGateResponse>(`${API_PREFIX}/ops/retry/custody-gate`, null, {
    params: { bundle_id: bundleId },
  });
  return data;
}

export async function reconcilePipeline(
  shipmentId?: string,
  executeRepair = false,
): Promise<ReconcileResponse> {
  const { data } = await apiClient.post<ReconcileResponse>(`${API_PREFIX}/ops/reconcile`, null, {
    params: {
      shipment_id: shipmentId,
      execute_repair: executeRepair,
    },
  });
  return data;
}

export async function reprocessDeadLetter(
  limit = 100,
  deleteRequeued = false,
): Promise<DeadLetterReprocessResponse> {
  const { data } = await apiClient.post<DeadLetterReprocessResponse>(`${API_PREFIX}/ops/reprocess/dead-letter`, null, {
    params: {
      limit,
      delete_requeued: deleteRequeued,
    },
  });
  return data;
}

export async function getWorkersStatus(): Promise<WorkersStatusResponse> {
  const { data } = await apiClient.get<WorkersStatusResponse>(`${API_PREFIX}/ops/workers/status`);
  return data;
}
