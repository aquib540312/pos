import axios from 'axios'
import { useAuthStore } from '../store/auth'

// Local dev (and docker-compose) rely on a same-origin reverse proxy for
// /api/v1 (see vite.config.ts / nginx.conf), so a relative path is enough.
// When the frontend and backend are deployed as two separate services with
// no shared proxy in front of them (e.g. Render: a static site + a
// standalone web service, each on its own onrender.com subdomain),
// VITE_API_HOST names the backend's real host at build time and every
// request goes straight to it instead.
// Render's fromService "host" property (see render.yaml) resolves to the
// service's private-network hostname slug, e.g. "pos-backend-a1b2" -- NOT
// a resolvable domain on its own. The browser running this bundle has no
// access to Render's private network at all; it needs the real public
// hostname, which is that same slug with .onrender.com appended.
//
// The Electron desktop shell (see desktop/) has no reverse proxy in front
// of it either, but unlike Render its backend URL isn't known at build
// time -- one installer gets used against whichever branch's backend a
// shop points it at, configured at runtime through the desktop shell's
// settings window. Its preload script exposes that as
// window.__POS_DESKTOP__.apiBaseUrl before this module ever runs, so it
// takes priority over the build-time envs below.
declare global {
  interface Window {
    __POS_DESKTOP__?: { apiBaseUrl?: string }
  }
}

const apiBaseUrl =
  window.__POS_DESKTOP__?.apiBaseUrl ||
  (import.meta.env.VITE_API_HOST
    ? `https://${import.meta.env.VITE_API_HOST}.onrender.com/api/v1`
    : '/api/v1')

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg ?? JSON.stringify(d)).join(', ')
  }
  return 'Something went wrong. Please try again.'
}
