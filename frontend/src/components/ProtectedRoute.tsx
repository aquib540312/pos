import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/auth'

export default function ProtectedRoute() {
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)
  const setSession = useAuthStore((s) => s.setSession)
  const logout = useAuthStore((s) => s.logout)
  // The auth store only persists the token (see store/auth.ts); `user` is
  // in-memory only, set once at login. Any full page load/reload after that
  // -- a browser refresh, a bookmarked URL, this test suite's page.goto --
  // starts with token present but user null, and pages that read
  // user?.id (e.g. StaffPage's self-deactivation guard) would silently
  // misbehave without this rehydration.
  const [rehydrating, setRehydrating] = useState(Boolean(token) && !user)

  useEffect(() => {
    if (token && !user) {
      apiClient
        .get('/auth/me')
        .then((res) => setSession(token, res.data))
        .catch(() => logout())
        .finally(() => setRehydrating(false))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!token) {
    return <Navigate to="/login" replace />
  }
  if (rehydrating) {
    return null
  }
  return <Outlet />
}
