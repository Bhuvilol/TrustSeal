import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { Device, DeviceCreatePayload, DeviceStatus, DeviceUpdatePayload } from '@/types';

interface DeviceQueryParams {
  skip?: number;
  limit?: number;
  status?: DeviceStatus;
}

export async function getDevices(params?: DeviceQueryParams): Promise<Device[]> {
  const { data } = await apiClient.get<Device[]>(`${API_PREFIX}/devices/`, { params });
  return data;
}

export async function getDeviceById(deviceId: string): Promise<Device> {
  const { data } = await apiClient.get<Device>(`${API_PREFIX}/devices/${deviceId}`);
  return data;
}

export async function createDevice(payload: DeviceCreatePayload): Promise<Device> {
  const { data } = await apiClient.post<Device>(`${API_PREFIX}/devices/`, payload);
  return data;
}

export async function updateDevice(deviceId: string, payload: DeviceUpdatePayload): Promise<Device> {
  const { data } = await apiClient.put<Device>(`${API_PREFIX}/devices/${deviceId}`, payload);
  return data;
}

export async function deleteDevice(deviceId: string): Promise<{ message: string }> {
  const { data } = await apiClient.delete<{ message: string }>(`${API_PREFIX}/devices/${deviceId}`);
  return data;
}
