import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';

type ApiEnvelope<T extends Record<string, unknown>> = {
  success: boolean;
  data: T;
  request_id: string;
  timestamp: string;
};

export type TelemetryIngestPayload = {
  event_id: string;
  shipment_id: string;
  device_id: string;
  device_uid?: string;
  ts: string;
  seq_no: number;
  temperature_c?: number;
  humidity_pct?: number;
  shock_g?: number;
  light_lux?: number;
  tilt_deg?: number;
  gps?: { lat: number; lng: number; speed_kmh?: number; heading_deg?: number };
  battery_pct?: number;
  network_type?: string;
  firmware_version?: string;
  hash_alg: string;
  payload_hash: string;
  sig_alg: string;
  signature: string;
  pubkey_id: string;
  idempotency_key: string;
};

export type CustodyIngestPayload = {
  custody_event_id: string;
  shipment_id: string;
  leg_id: string;
  verifier_device_id: string;
  verifier_user_id: string;
  ts: string;
  fingerprint_result: 'match' | 'no_match' | 'error';
  fingerprint_score?: number;
  fingerprint_template_id?: string;
  digital_signer_address: string;
  approval_message_hash: string;
  signature: string;
  sig_alg: string;
  idempotency_key: string;
};

export async function ingestTelemetry(payload: TelemetryIngestPayload): Promise<ApiEnvelope<Record<string, unknown>>> {
  const { data } = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(`${API_PREFIX}/ingest/telemetry`, payload);
  return data;
}

export async function ingestCustody(payload: CustodyIngestPayload): Promise<ApiEnvelope<Record<string, unknown>>> {
  const { data } = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(`${API_PREFIX}/ingest/custody`, payload);
  return data;
}

