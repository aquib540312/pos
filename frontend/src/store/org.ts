import { create } from 'zustand'
import type { OrgProfile } from '../types'

interface OrgState {
  profile: OrgProfile | null
  setProfile: (p: OrgProfile) => void
}

export const useOrgStore = create<OrgState>((set) => ({
  profile: null,
  setProfile: (profile) => set({ profile }),
}))

export function useTaxMode(): string {
  return useOrgStore((s) => s.profile?.tax_mode ?? 'saudi')
}
