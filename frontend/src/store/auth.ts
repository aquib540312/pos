import { create } from 'zustand'

export interface AuthUser {
  id: string
  full_name: string
  email: string
  role_ids: string[]
  role_names: string[]
  permissions: string[]
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  setSession: (token: string, user: AuthUser) => void
  logout: () => void
}

const STORAGE_KEY = 'pos_auth_token'
const USER_KEY = 'pos_auth_user'

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem(STORAGE_KEY),
  user: (() => {
    try {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })(),
  setSession: (token, user) => {
    localStorage.setItem(STORAGE_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    set({ token, user })
  },
  logout: () => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(USER_KEY)
    set({ token: null, user: null })
  },
}))

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY && !e.newValue) {
      useAuthStore.getState().logout()
    }
  })
}
