import type { UserRole } from '@/types';

type Permission =
  | 'manage_devices'
  | 'create_shipments'
  | 'manage_legs'
  | 'manage_checkpoints'
  | 'update_shipment_status'
  | 'manage_operations';

const rolePermissions: Record<UserRole, Permission[]> = {
  admin: ['manage_devices', 'create_shipments', 'manage_legs', 'manage_checkpoints', 'update_shipment_status', 'manage_operations'],
  factory: ['manage_devices', 'create_shipments', 'manage_legs', 'update_shipment_status'],
  port: [],
  warehouse: [],
  customer: ['manage_checkpoints'],
  authority: ['manage_operations'],
};

export function hasPermission(role: UserRole | undefined, permission: Permission): boolean {
  if (!role) {
    return false;
  }

  return rolePermissions[role]?.includes(permission) ?? false;
}
