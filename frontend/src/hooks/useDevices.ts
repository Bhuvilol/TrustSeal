import { useQuery } from '@tanstack/react-query';
import { getDeviceById, getDevices } from '@/api/devices';
import type { DeviceStatus } from '@/types';

interface DeviceListFilters {
  status?: DeviceStatus;
}

export function useDevices(filters?: DeviceListFilters) {
  const status = filters?.status;

  return useQuery({
    queryKey: ['devices', status ?? 'all'],
    queryFn: () => getDevices(status ? { status } : undefined),
    retry: 0,
    staleTime: 3 * 60_000,
    gcTime: 10 * 60_000,
  });
}

export function useDevice(deviceId: string | undefined) {
  return useQuery({
    queryKey: ['device', deviceId],
    queryFn: () => getDeviceById(deviceId as string),
    enabled: Boolean(deviceId),
    retry: 0,
    staleTime: 3 * 60_000,
    gcTime: 10 * 60_000,
  });
}

