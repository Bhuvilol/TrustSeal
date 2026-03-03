import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type {
  CustodyCheckpointCreatePayload,
  CustodyCheckpoint,
  SensorLog,
  Shipment,
  ShipmentCreatePayload,
  ShipmentLeg,
  ShipmentLegCreatePayload,
  ShipmentSensorStats,
  ShipmentStatus,
  ShipmentUpdatePayload,
  ShipmentWithDetails,
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

export async function getShipmentLogs(shipmentId: string): Promise<SensorLog[]> {
  const { data } = await apiClient.get<SensorLog[]>(`${API_PREFIX}/shipments/${shipmentId}/logs`);
  return data;
}

export async function getShipmentLogsWithParams(
  shipmentId: string,
  params?: { skip?: number; limit?: number },
): Promise<SensorLog[]> {
  const { data } = await apiClient.get<SensorLog[]>(`${API_PREFIX}/shipments/${shipmentId}/logs`, { params });
  return data;
}

interface TelemetryQueryParams {
  skip?: number;
  limit?: number;
}

export async function getShipmentTelemetry(
  shipmentId: string,
  params?: TelemetryQueryParams,
): Promise<SensorLog[]> {
  try {
    const { data } = await apiClient.get<SensorLog[]>(
      `${API_PREFIX}/shipments/${shipmentId}/telemetry`,
      { params, timeout: 8_000 },
    );
    return data;
  } catch {
    const { data } = await apiClient.get<SensorLog[]>(`${API_PREFIX}/shipments/${shipmentId}/logs`, {
      params,
      timeout: 8_000,
    });
    return data;
  }
}

export async function getShipmentSensorStats(shipmentId: string): Promise<ShipmentSensorStats> {
  const { data } = await apiClient.get<ShipmentSensorStats>(`${API_PREFIX}/shipments/${shipmentId}/sensor-stats`);
  return data;
}

export async function getShipmentLegs(shipmentId: string): Promise<ShipmentLeg[]> {
  const { data } = await apiClient.get<ShipmentLeg[]>(`${API_PREFIX}/legs/`, {
    params: { shipment_id: shipmentId },
  });
  return data;
}

export async function getShipmentCustody(shipmentId: string): Promise<CustodyCheckpoint[]> {
  const { data } = await apiClient.get<CustodyCheckpoint[]>(`${API_PREFIX}/custody/`, {
    params: { shipment_id: shipmentId },
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

export async function createCustodyCheckpoint(
  payload: CustodyCheckpointCreatePayload,
): Promise<CustodyCheckpoint> {
  const { data } = await apiClient.post<CustodyCheckpoint>(`${API_PREFIX}/custody/`, payload);
  return data;
}
