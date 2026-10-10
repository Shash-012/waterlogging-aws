// Stand-in for Cognito until the wlew-ops user pool exists. It accepts any
// username and password and issues an unsigned token, which the real ops API
// would reject; in fixtures mode alerts are faked locally, so that's fine.
import { sessionFromIdToken } from './session'
import { AuthError, type AuthClient, type Session } from './types'

const MIN_PASSWORD = 8

function b64url(s: string): string {
  const bytes = new TextEncoder().encode(s)
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fakeToken(username: string): string {
  const exp = Math.floor(Date.now() / 1000) + 3600
  return `${b64url('{"alg":"none"}')}.${b64url(JSON.stringify({ 'cognito:username': username, exp }))}.demo`
}

export const demoAuth: AuthClient = {
  kind: 'demo',

  async signIn(username, password) {
    const name = username.trim()
    if (!name || !password) throw new AuthError('invalid', 'Enter a username and password.')
    // Lets the first-sign-in flow be tried without Cognito.
    if (name.toLowerCase().startsWith('new')) {
      return { kind: 'newPasswordRequired', username: name, challenge: 'demo' }
    }
    return { kind: 'signedIn', session: sessionFromIdToken(fakeToken(name), name) }
  },

  async completeNewPassword(step, newPassword): Promise<Session> {
    if (newPassword.length < MIN_PASSWORD) {
      throw new AuthError('InvalidPasswordException', `Password must be at least ${MIN_PASSWORD} characters.`)
    }
    return sessionFromIdToken(fakeToken(step.username), step.username)
  },

  async signOut() {},
}
