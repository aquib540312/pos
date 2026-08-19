import { useAuthStore, type AuthUser } from '../store/auth'

// Mirrors the backend permission codes (app/core/permissions.py Perm).
export const PERMS = {
  USERS_MANAGE: 'users:manage',
  ROLES_MANAGE: 'roles:manage',
  CATALOG_VIEW: 'catalog:view',
  CATALOG_MANAGE: 'catalog:manage',
  INVENTORY_VIEW: 'inventory:view',
  INVENTORY_ADJUST: 'inventory:adjust',
  PARTY_MANAGE: 'party:manage',
  PURCHASE_CREATE: 'purchase:create',
  PURCHASE_RECEIVE: 'purchase:receive',
  SALES_CREATE: 'sales:create',
  SALES_RETURN: 'sales:return',
  QUOTATION_CREATE: 'quotation:create',
  SHIFT_MANAGE: 'shift:manage',
  DINING_VIEW: 'dining:view',
  DINING_MANAGE: 'dining:manage',
  REPORTS_VIEW: 'reports:view',
  ORG_MANAGE: 'org:manage',
  SYNC_MANAGE: 'sync:manage',
} as const

export type PermissionCode = (typeof PERMS)[keyof typeof PERMS] | string

/**
 * True when the user holds ANY of the given permission(s). The backend
 * remains the source of truth -- this is UX gating only, every protected
 * endpoint still enforces permissions server-side.
 */
export function can(required: PermissionCode | PermissionCode[], user: AuthUser | null): boolean {
  if (!user || !Array.isArray(user.permissions)) return false
  const codes = Array.isArray(required) ? required : [required]
  return codes.some((code) => user.permissions.includes(code))
}

export function useCan(required: PermissionCode | PermissionCode[]): boolean {
  const user = useAuthStore((s) => s.user)
  return can(required, user)
}