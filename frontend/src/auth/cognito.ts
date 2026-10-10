// Cognito sign-in over its public JSON API, no SDK needed. Requires the
// wlew-ops app client to have no client secret and ALLOW_USER_PASSWORD_AUTH
// enabled (plus ALLOW_REFRESH_TOKEN_AUTH, which Cognito always wants).
import { sessionFromIdToken } from './session'
import { AuthError, type AuthClient, type SignInStep } from './types'

interface CognitoConfig {
  userPoolId: string
  clientId: string
}

interface AuthResponse {
  AuthenticationResult?: { IdToken: string }
  ChallengeName?: string
  Session?: string
}

const MESSAGES: Record<string, string> = {
  NotAuthorizedException: 'Wrong username or password.',
  UserNotFoundException: 'Wrong username or password.',
  PasswordResetRequiredException: 'An admin has reset this password. Ask them for a new temporary one.',
  InvalidPasswordException: "That password doesn't meet the policy: at least 8 characters with upper case, lower case, a number and a symbol.",
  TooManyRequestsException: 'Too many attempts. Wait a minute and try again.',
  LimitExceededException: 'Too many attempts. Wait a minute and try again.',
}

export function createCognitoAuth({ userPoolId, clientId }: CognitoConfig): AuthClient {
  // Pool ids look like "ap-south-1_AbCdEf123"; the region is the prefix.
  const region = userPoolId.split('_')[0]
  const endpoint = `https://cognito-idp.${region}.amazonaws.com/`

  async function call(action: string, body: object): Promise<AuthResponse> {
    let res: Response
    try {
      res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': `AWSCognitoIdentityProviderService.${action}`,
        },
        body: JSON.stringify(body),
      })
    } catch {
      throw new AuthError('network', "Can't reach the sign-in service. Check your connection.")
    }
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const code = String(data.__type ?? 'unknown').split('#').pop()!
      throw new AuthError(code, MESSAGES[code] ?? data.message ?? 'Sign-in failed.')
    }
    return data
  }

  function toStep(username: string, r: AuthResponse): SignInStep {
    if (r.AuthenticationResult) {
      return { kind: 'signedIn', session: sessionFromIdToken(r.AuthenticationResult.IdToken, username) }
    }
    if (r.ChallengeName === 'NEW_PASSWORD_REQUIRED' && r.Session) {
      return { kind: 'newPasswordRequired', username, challenge: r.Session }
    }
    throw new AuthError('unsupported', `Unsupported sign-in step: ${r.ChallengeName ?? 'none'}.`)
  }

  return {
    kind: 'cognito',

    async signIn(username, password) {
      const name = username.trim()
      if (!name || !password) throw new AuthError('invalid', 'Enter a username and password.')
      const r = await call('InitiateAuth', {
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: clientId,
        AuthParameters: { USERNAME: name, PASSWORD: password },
      })
      return toStep(name, r)
    },

    async completeNewPassword(step, newPassword) {
      const r = await call('RespondToAuthChallenge', {
        ChallengeName: 'NEW_PASSWORD_REQUIRED',
        ClientId: clientId,
        Session: step.challenge,
        ChallengeResponses: { USERNAME: step.username, NEW_PASSWORD: newPassword },
      })
      const next = toStep(step.username, r)
      if (next.kind !== 'signedIn') throw new AuthError('unsupported', 'Sign-in needs another step.')
      return next.session
    },

    // Tokens live only in this tab's sessionStorage, which sign-out clears.
    async signOut() {},
  }
}

export function authFromEnv(env: ImportMetaEnv = import.meta.env): AuthClient | null {
  const userPoolId = env.VITE_COGNITO_USER_POOL_ID?.trim()
  const clientId = env.VITE_COGNITO_CLIENT_ID?.trim()
  return userPoolId && clientId ? createCognitoAuth({ userPoolId, clientId }) : null
}
