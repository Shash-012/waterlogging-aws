import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authFromEnv } from './cognito'
import { AuthContext } from './context'
import { demoAuth } from './demo'
import { clearSession, isExpired, loadSession, saveSession } from './session'
import type { AuthClient, Session } from './types'

interface Props {
  children: ReactNode
  // Tests pass these; the app uses Cognito when configured, else the demo login.
  client?: AuthClient
  initialSession?: Session | null
}

export function AuthProvider({ children, client, initialSession }: Props) {
  const auth = useMemo(() => client ?? authFromEnv() ?? demoAuth, [client])
  const [session, setSessionState] = useState<Session | null>(() =>
    initialSession !== undefined ? initialSession : loadSession(),
  )

  const setSession = useCallback((s: Session) => {
    saveSession(s)
    setSessionState(s)
  }, [])

  const signOut = useCallback(() => {
    if (session) auth.signOut(session).catch(() => {})
    clearSession()
    setSessionState(null)
  }, [auth, session])

  // Drop back to the sign-in screen when the token runs out.
  useEffect(() => {
    if (!session) return
    if (isExpired(session)) {
      signOut()
      return
    }
    const t = setTimeout(signOut, Math.max(0, session.expiresAt - 60_000 - Date.now()))
    return () => clearTimeout(t)
  }, [session, signOut])

  const value = useMemo(() => ({ client: auth, session, setSession, signOut }), [auth, session, setSession, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
