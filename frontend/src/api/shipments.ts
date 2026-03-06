import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type {
  CustodyTransfer,
  Shipment,
  ShipmentCreatePayload,
  ShipmentLeg,
  ShipmentLegCreatePayload,
  ShipmentOverview,
  ShipmentSensorStats,
  ShipmentStatus,
  ShipmentUpdatePayload,
  ShipmentWithDetails,
  TelemetryEvent,
} from '@/types';

interface ShipmentQueryParams {
  skip?: number;
  limit?: number;
  status?: ShipmentStatus;
  device_id?: string;
}

export async function getShipments(params?: ShipmentQueryParams): Promise<Shipment[]> {
  const { data } = await apiClient.get<Shipment[]>(`${API_PREFIX}/shipments/`, { params });
  return data;
}

export async function getShipmentsByDevice(deviceId: string): Promise<Shipment[]> {
  return getShipments({ device_id: deviceId });
}

export async function getShipmentById(shipmentId: string): Promise<ShipmentWithDetails> {
  const { data } = await apiClient.get<ShipmentWithDetails>(`${API_PREFIX}/shipments/${shipmentId}`);
  return data;
}

export async function createShipment(payload: ShipmentCreatePayload): Promise<Shipment> {
  const { data } = await apiClient.post<Shipment>(`${API_PREFIX}/shipments/`, payload);
  return data;
}

export async function updateShipment(shipmentId: string, payload: ShipmentUpdatePayload): Promise<Shipment> {
  const { data } = await apiClient.put<Shipment>(`${API_PREFIX}/shipments/${shipmentId}`, payload);
  return data;
}

interface TelemetryQueryParams {
  skip?: number;
  limit?: number;
  from?: string;
  to?: string;
}

export async function getShipmentTelemetry(
  shipmentId: string,
  params?: TelemetryQueryParams,
): Promise<TelemetryEvent[]> {
  const { data } = await apiClient.get<TelemetryEvent[]>(`${API_PREFIX}/shipments/${shipmentId}/telemetry`, {
    params,
    timeout: 8_000,
  });
  return data;
}

export async function getShipmentSensorStats(shipmentId: string): Promise<ShipmentSensorStats> {
  const { data } = await apiClient.get<ShipmentSensorStats>(`${API_PREFIX}/shipments/${shipmentId}/sensor-stats`);
  return data;
}

export async function getShipmentLegs(shipmentId: string): Promise<ShipmentLeg[]> {
  const { data } = await apiClient.get<ShipmentLeg[]>(`${API_PREFIX}/shipments/${shipmentId}/legs`);
  return data;
}

export async function getShipmentOverview(shipmentId: string): Promise<ShipmentOverview> {
  const { data } = await apiClient.get<ShipmentOverview>(`${API_PREFIX}/shipments/${shipmentId}/overview`);
  return data;
}

interface CustodyQueryParams {
  skip?: number;
  limit?: number;
  from?: string;
  to?: string;
}

export async function getShipmentCustody(
  shipmentId: string,
  params?: CustodyQueryParams,
): Promise<CustodyTransfer[]> {
  const { data } = await apiClient.get<CustodyTransfer[]>(`${API_PREFIX}/shipments/${shipmentId}/custody`, {
    params,
    timeout: 8_000,
  });
  return data;
}

export async function createShipmentLeg(payload: ShipmentLegCreatePayload): Promise<ShipmentLeg> {
  const { data } = await apiClient.post<ShipmentLeg>(`${API_PREFIX}/legs/`, payload);
  return data;
}

export async function startShipmentLeg(legId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(`${API_PREFIX}/legs/${legId}/start`);
  return data;
}

export async function completeShipmentLeg(legId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(`${API_PREFIX}/legs/${legId}/complete`);
  return data;
}
