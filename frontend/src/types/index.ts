export type UserRole = 'factory' | 'port' | 'warehouse' | 'customer' | 'admin' | 'authority';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  created_at: string;
  is_active: boolean;
  is_verified: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role?: UserRole;
  user_id?: string;
}

export interface RegisterPayload {
  email: string;
  name: string;
  password: string;
  role: UserRole;
}

export interface RegisterResponse {
  user: User;
  access_token: string;
  token_type: string;
  verification_token: string;
  verification_token_expires_at: string;
}

export type DeviceStatus = 'active' | 'inactive' | 'maintenance';

export interface Device {
  id: string;
  device_uid: string;
  model: string;
  firmware_version: string;
  battery_capacity_mAh: number | null;
  status: DeviceStatus;
  created_at: string;
}

export interface DeviceCreatePayload {
  device_uid: string;
  model: string;
  firmware_version: string;
  battery_capacity_mAh: number | null;
  status: DeviceStatus;
}

export interface DeviceUpdatePayload {
  model?: string;
  firmware_version?: string;
  battery_capacity_mAh?: number | null;
  status?: DeviceStatus;
}

export type ShipmentStatus = 'created' | 'in_transit' | 'docking' | 'completed' | 'compromised';

export interface Shipment {
  id: string;
  shipment_code: string;
  description: string | null;
  origin: string;
  destination: string;
  status: ShipmentStatus;
  device_id: string;
  created_at: string;
}

export interface ShipmentCreatePayload {
  shipment_code: string;
  description: string | null;
  origin: string;
  destination: string;
  device_id: string;
}

export interface ShipmentUpdatePayload {
  description?: string | null;
  origin?: string;
  destination?: string;
  status?: ShipmentStatus;
  device_id?: string;
}

export type LegStatus = 'pending' | 'in_progress' | 'settled';

export interface ShipmentLeg {
  id: string;
  shipment_id: string;
  leg_number: number;
  from_location: string;
  to_location: string;
  status: LegStatus;
  started_at: string | null;
  completed_at: string | null;
}

export interface ShipmentLegCreatePayload {
  shipment_id: string;
  leg_number: number;
  from_location: string;
  to_location: string;
}

export interface ShipmentSensorStats {
  shipment_id: string;
  total_logs: number;
  temperature_sample_count: number;
  average_temperature: number | null;
  min_temperature: number | null;
  max_temperature: number | null;
  max_shock: number | null;
  first_recorded_at: string | null;
  last_recorded_at: string | null;
  has_temperature_breach: boolean;
}

export interface TelemetryUpdateEvent {
  event: 'telemetry-update';
  shipment_id: string;
  latitude: number;
  longitude: number;
  temperature: number | null;
  humidity: number | null;
  shock: number | null;
  tilt_angle: number | null;
  speed?: number | null;
  heading?: number | null;
  timestamp: string;
}

export interface CustodyTransfer {
  custody_event_id: string;
  shipment_id: string;
  leg_id: string | null;
  verifier_user_id: string | null;
  verifier_device_id: string | null;
  ts: string | null;
  fingerprint_result: string | null;
  fingerprint_score: number | null;
  digital_signer_address: string | null;
  approval_hash: string | null;
  verification_status: string | null;
  ingest_status: string | null;
  created_at: string;
}

export interface TelemetryEvent {
  event_id: string;
  shipment_id: string;
  device_id: string;
  ts: string;
  seq_no: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  shock_g: number | null;
  light_lux: number | null;
  tilt_deg: number | null;
  gps: {
    lat: number;
    lng: number;
    speed_kmh?: number;
    heading_deg?: number;
  } | null;
  battery_pct: number | null;
  network_type: string | null;
  firmware_version: string | null;
  bundle_id: string | null;
  payload_hash: string;
  signature: string | null;
  verification_status: string | null;
  ingest_status: string | null;
  created_at: string;
}

export interface ShipmentWithDetails extends Shipment {
  device?: Device | null;
  legs?: ShipmentLeg[];
}

export interface ShipmentOverview {
  shipment: ShipmentWithDetails;
  latest_bundle: {
    bundle_id: string;
    status: string;
    record_count: number;
    batch_hash: string;
    ipfs_cid: string | null;
    tx_hash: string | null;
    anchor_status: string | null;
    anchored_at: string | null;
    created_at: string | null;
  } | null;
}

export interface ApiErrorPayload {
  detail?: string;
  message?: string;
}

export type ChatConfidence = 'high' | 'medium' | 'low';

export interface ChatResponse {
  answer: string;
  sources: string[];
  confidence: ChatConfidence;
  session_id?: string | null;
}

export interface BundleIpfsProof {
  cid: string | null;
  pin_status: string | null;
  pinned_at: string | null;
  content_hash?: string | null;
  size_bytes?: number | null;
}

export interface BundleChainProof {
  network: string | null;
  contract_address: string | null;
  tx_hash: string | null;
  anchor_status: string | null;
  anchored_at: string | null;
  block_number?: number | null;
  error_message?: string | null;
}

export interface ShipmentLatestProof {
  shipment_id: string;
  bundle_id: string;
  epoch: number;
  status: string;
  record_count: number;
  batch_hash: string;
  ipfs: BundleIpfsProof;
  chain: BundleChainProof;
  created_at: string | null;
  error_message: string | null;
}

export interface BundleProof {
  bundle_id: string;
  shipment_id: string;
  epoch: number;
  status: string;
  record_count: number;
  batch_hash: string;
  ipfs: BundleIpfsProof;
  chain: BundleChainProof;
  created_at: string | null;
  error_message: string | null;
}

export interface BundleIpfsLink {
  bundle_id: string;
  shipment_id: string;
  ipfs_cid: string;
  gateway_url: string;
}

export interface PipelineStatusResponse {
  pipeline: {
    batch_status_counts: Record<string, number>;
    anchors_pending: number;
    anchors_failed: number;
    ipfs_pending: number;
  };
  redis: {
    available: boolean;
    telemetry_stream_len?: number;
    custody_stream_len?: number;
    bundle_ready_stream_len?: number;
    anchor_request_stream_len?: number;
    dead_letter_stream_len?: number;
    error?: string;
  };
  workers?: {
    started: boolean;
    healthy: boolean;
  };
  shipment?: {
    shipment_id: string;
    ingest: string;
    batch: string;
    custody: string;
    anchor: string;
    latest_bundle_id: string | null;
    latest_ipfs_cid: string | null;
    latest_tx_hash: string | null;
    updated_at: string | null;
    error_message: string | null;
  };
}

export interface RetryAnchorResponse {
  accepted: boolean;
  bundle_id: string;
  shipment_id: string;
  batch_status: string;
  anchor_status: string;
}

export interface RetryIpfsResponse {
  accepted: boolean;
  bundle_id: string;
  shipment_id: string;
  batch_status: string;
  ipfs_cid: string | null;
  pin_status: string;
}

export interface RetryCustodyGateResponse {
  accepted: boolean;
  bundle_id: string;
  shipment_id: string;
  batch_status: string;
  custody_verified: boolean;
  anchor_status: string | null;
}

export interface ReconcileResponse {
  shipment_scope: string;
  scanned_batches: number;
  missing_ipfs_rows: string[];
  missing_anchor_rows: string[];
  repair_executed: boolean;
  repaired_bundle_ids: string[];
}

export interface DeadLetterReprocessResponse {
  accepted: boolean;
  dead_letter_stream: string;
  scanned: number;
  requeued: number;
  skipped: number;
  failed: number;
  delete_requeued: boolean;
}

export interface WorkerSnapshot {
  name?: string;
  running?: boolean;
  status?: string;
  thread_alive?: boolean;
  last_heartbeat?: string | null;
  error?: string | null;
  restart_count?: number;
  [key: string]: unknown;
}

export interface WorkersStatusResponse {
  orchestrator: {
    started: boolean;
    healthy: boolean;
    shutdown_requested: boolean;
  };
  workers: Record<string, WorkerSnapshot>;
}
