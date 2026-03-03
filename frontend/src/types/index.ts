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

export interface SensorLog {
  id: string;
  shipment_id: string;
  temperature: number | null;
  humidity: number | null;
  shock: number | null;
  light_exposure: boolean | null;
  tilt_angle: number | null;
  latitude: number | null;
  longitude: number | null;
  speed?: number | null;
  heading?: number | null;
  hash_value: string;
  recorded_at: string;
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

export interface CustodyCheckpoint {
  id: string;
  shipment_id: string;
  leg_id: string | null;
  verified_by: string | null;
  biometric_verified: boolean | null;
  blockchain_tx_hash: string | null;
  merkle_root_hash: string | null;
  timestamp: string;
}

export interface CustodyCheckpointCreatePayload {
  shipment_id: string;
  leg_id: string | null;
  biometric_verified: boolean;
  blockchain_tx_hash: string | null;
  merkle_root_hash: string | null;
}

export interface ShipmentWithDetails extends Shipment {
  device?: Device | null;
  legs?: ShipmentLeg[];
  sensor_logs?: SensorLog[];
  custody_checkpoints?: CustodyCheckpoint[];
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
