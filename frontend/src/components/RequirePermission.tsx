import type { ReactNode } from 'react'
import { can, type PermissionCode } from '../auth/permissions'
import { useAuthStore } from '../store/auth'
import AccessDeniedPage from '../pages/AccessDeniedPage'

// Route-level gate: render children when the user holds the permission,
// otherwise a proper access-denied message. Authentication itself is still
// handled by ProtectedRoute (which also awaits /auth/me before rendering,
// so user is populated here).
export default function RequirePermission({
  permission,
  children,
}: {
  permission: PermissionCode | PermissionCode[]
  children: ReactNode
}) {
  const user = useAuthStore((s) => s.user)
  if (!can(permission, user)) {
    return <AccessDeniedPage />
  }
  return <>{children}</>
}