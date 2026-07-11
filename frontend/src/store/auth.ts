import { create } from 'zustand'

export interface AuthUser {
  id: string
  full_name: string
  email: string
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  setSession: (token: string, user: AuthUser) => void
  logout: () => void
}

const STORAGE_KEY = 'pos_auth_token'

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem(STORAGE_KEY),
  user: null,
  setSession: (token, user) => {
    localStorage.setItem(STORAGE_KEY, token)
    set({ token, user })
  },
  logout: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ token: null, user: null })
  },
}))
