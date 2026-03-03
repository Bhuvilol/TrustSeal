import { useQuery } from '@tanstack/react-query';
import {
  getShipmentById,
  getShipmentCustody,
  getShipmentLegs,
  getShipmentLogs,
  getShipmentLogsWithParams,
  getShipmentSensorStats,
  getShipmentTelemetry,
  getShipments,
  getShipmentsByDevice,
} from '@/api/shipments';
import type { ShipmentStatus } from '@/types';

interface ShipmentListFilters {
  status?: ShipmentStatus;
}

export function useShipments(filters?: ShipmentListFilters) {
  const status = filters?.status;

  return useQuery({
    queryKey: ['shipments', status ?? 'all'],
    queryFn: () => getShipments(status ? { status } : undefined),
    retry: 0,
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useDeviceShipments(deviceId: string | undefined) {
  return useQuery({
    queryKey: ['shipments', 'device', deviceId],
    queryFn: () => getShipmentsByDevice(deviceId as string),
    enabled: Boolean(deviceId),
    retry: 0,
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useShipment(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId],
    queryFn: () => getShipmentById(shipmentId as string),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useShipmentLogs(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'logs'],
    queryFn: () => getShipmentLogs(shipmentId as string),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}

interface QueryOptions {
  enabled?: boolean;
}

export function useShipmentLogsWithParams(
  shipmentId: string | undefined,
  filters?: TelemetryFilters,
  options?: QueryOptions,
) {
  const skip = filters?.skip ?? 0;
  const limit = filters?.limit ?? 1000;
  const enabled = options?.enabled ?? Boolean(shipmentId);

  return useQuery({
    queryKey: ['shipment', shipmentId, 'logs', skip, limit],
    queryFn: () => getShipmentLogsWithParams(shipmentId as string, { skip, limit }),
    enabled,
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    placeholderData: (previousData) => previousData,
  });
}

interface TelemetryFilters {
  skip?: number;
  limit?: number;
}

export function useShipmentTelemetry(shipmentId: string | undefined, filters?: TelemetryFilters) {
  const skip = filters?.skip ?? 0;
  const limit = filters?.limit ?? 1000;

  return useQuery({
    queryKey: ['shipment', shipmentId, 'telemetry', skip, limit],
    queryFn: () => getShipmentTelemetry(shipmentId as string, { skip, limit }),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    placeholderData: (previousData) => previousData,
  });
}

export function useShipmentSensorStats(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'sensor-stats'],
    queryFn: () => getShipmentSensorStats(shipmentId as string),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 20_000,
    gcTime: 5 * 60_000,
    placeholderData: (previousData) => previousData,
  });
}

export function useShipmentLegs(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'legs'],
    queryFn: () => getShipmentLegs(shipmentId as string),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    placeholderData: (previousData) => previousData,
  });
}

export function useShipmentCustody(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'custody'],
    queryFn: () => getShipmentCustody(shipmentId as string),
    enabled: Boolean(shipmentId),
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    placeholderData: (previousData) => previousData,
  });
}

