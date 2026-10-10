import { createContext, useContext } from 'react'
import type { AuthClient, Session } from './types'

export interface AuthState {
  client: AuthClient
  session: Session | null
  setSession: (s: Session) => void
  signOut: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
