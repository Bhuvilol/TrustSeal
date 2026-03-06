import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { BundleIpfsLink, BundleProof, ShipmentLatestProof } from '@/types';

export async function getLatestShipmentProof(shipmentId: string): Promise<ShipmentLatestProof> {
  const { data } = await apiClient.get<ShipmentLatestProof>(`${API_PREFIX}/proofs/shipments/${shipmentId}/latest`);
  return data;
}

export async function getBundleProof(bundleId: string): Promise<BundleProof> {
  const { data } = await apiClient.get<BundleProof>(`${API_PREFIX}/proofs/bundles/${bundleId}`);
  return data;
}

export async function getBundleIpfsLink(bundleId: string): Promise<BundleIpfsLink> {
  const { data } = await apiClient.get<BundleIpfsLink>(`${API_PREFIX}/proofs/bundles/${bundleId}/ipfs-link`);
  return data;
}

