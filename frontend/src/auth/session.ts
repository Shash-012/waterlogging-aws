import type { Session } from './types'

// sessionStorage: the sign-in lasts until the tab closes, and never outlives the token.
const KEY = 'wlew.session'

function readJwtPayload(token: string): Record<string, unknown> | null {
  const part = token.split('.')[1]
  if (!part) return null
  try {
    const b64 = part.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      Array.from(atob(b64), (c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join(''),
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

export function sessionFromIdToken(idToken: string, fallbackUsername: string): Session {
  const claims = readJwtPayload(idToken) ?? {}
  const exp = typeof claims.exp === 'number' ? claims.exp * 1000 : Date.now() + 3_600_000
  const username =
    (claims['cognito:username'] as string | undefined) ?? (claims.email as string | undefined) ?? fallbackUsername
  return { username, idToken, expiresAt: exp }
}

export function isExpired(session: Session, now = Date.now()): boolean {
  // Treat the last minute as expired so a call never leaves with a dying token.
  return now >= session.expiresAt - 60_000
}

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as Session
    if (typeof s?.idToken !== 'string' || typeof s.expiresAt !== 'number' || isExpired(s)) {
      sessionStorage.removeItem(KEY)
      return null
    }
    return s
  } catch {
    return null
  }
}

export function saveSession(session: Session): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session))
  } catch {
    // Storage blocked: the sign-in still works for this page load.
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing stored.
  }
}
