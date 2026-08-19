import type { PermissionCode } from './permissions'
import { can, PERMS } from './permissions'
import type { AuthUser } from '../store/auth'

export interface NavItem {
  to: string
  label: string
  end?: boolean
  // Undefined means any authenticated user can see it. A list means ANY of
  // the listed permissions is enough.
  permission?: PermissionCode | PermissionCode[]
}

// Single source of truth for the sidebar: page -> permission mapping, also
// used for landing-page routing after login and the catch-all redirect.
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', end: true, permission: PERMS.REPORTS_VIEW },
  { to: '/pos', label: 'Billing (POS)', permission: PERMS.SALES_CREATE },
  { to: '/restaurant', label: 'Restaurant', permission: PERMS.DINING_MANAGE },
  { to: '/quotations', label: 'Quotations', permission: PERMS.QUOTATION_CREATE },
  { to: '/shift', label: 'Shift & Cash', permission: PERMS.SHIFT_MANAGE },
  { to: '/sales-history', label: 'Sales & Returns', permission: PERMS.REPORTS_VIEW },
  { to: '/products', label: 'Products', permission: PERMS.CATALOG_VIEW },
  { to: '/customers', label: 'Customers', permission: PERMS.PARTY_MANAGE },
  { to: '/suppliers', label: 'Suppliers', permission: PERMS.PARTY_MANAGE },
  { to: '/purchasing', label: 'Purchasing', permission: [PERMS.PURCHASE_CREATE, PERMS.PURCHASE_RECEIVE] },
  { to: '/stock', label: 'Stock', permission: PERMS.INVENTORY_VIEW },
  { to: '/stock-transfer', label: 'Stock Transfer', permission: PERMS.INVENTORY_VIEW },
  { to: '/staff', label: 'Staff', permission: PERMS.USERS_MANAGE },
  { to: '/roles', label: 'Roles', permission: PERMS.ROLES_MANAGE },
  { to: '/branches', label: 'Branches & Warehouses', permission: PERMS.ORG_MANAGE },
  { to: '/offers', label: 'Coupons & Gift Cards', permission: PERMS.CATALOG_MANAGE },
  { to: '/audit-log', label: 'Audit Log', permission: PERMS.ORG_MANAGE },
  { to: '/reports', label: 'Reports', permission: PERMS.REPORTS_VIEW },
  { to: '/sync', label: 'Sync Status', permission: PERMS.SYNC_MANAGE },
  { to: '/billing', label: 'Billing (Subscription)', permission: PERMS.ORG_MANAGE },
  { to: '/settings', label: 'Settings' },
]

export function visibleNavItems(user: AuthUser | null): NavItem[] {
  return NAV_ITEMS.filter((item) => (item.permission ? can(item.permission, user) : true))
}

// The page to land on after login / when hitting an unknown route: first
// permitted sidebar destination. Settings (change your own password) is the
// universal fallback so no locked-down user is dead-ended.
export function firstAllowedPath(user: AuthUser | null): string {
  const nav = visibleNavItems(user)
  if (nav.length > 0) return nav[0].to
  return '/settings'
}