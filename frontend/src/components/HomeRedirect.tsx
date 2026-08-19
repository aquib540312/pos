import { Navigate } from 'react-router-dom'
import { firstAllowedPath } from '../auth/nav'
import { useAuthStore } from '../store/auth'

// Landing page for the catch-all route: send every user to the first page
// they're actually allowed to see, instead of hard-coding '/' (which a
// cashier, lacking reports:view, would get a 403 from).
export default function HomeRedirect() {
  const user = useAuthStore((s) => s.user)
  return <Navigate to={firstAllowedPath(user)} replace />
}