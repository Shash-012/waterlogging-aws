export interface Session {
  username: string
  // Sent as "Authorization: Bearer <idToken>" on every ops API call.
  idToken: string
  // Epoch milliseconds, from the token's exp claim.
  expiresAt: number
}

// Officials are created by an admin with a temporary password, so the first
// sign-in asks them to choose a new one.
export type SignInStep =
  | { kind: 'signedIn'; session: Session }
  | { kind: 'newPasswordRequired'; username: string; challenge: string }

export interface AuthClient {
  // 'demo' means no real Cognito details are configured yet.
  kind: 'demo' | 'cognito'
  signIn(username: string, password: string): Promise<SignInStep>
  completeNewPassword(step: Extract<SignInStep, { kind: 'newPasswordRequired' }>, newPassword: string): Promise<Session>
  signOut(session: Session): Promise<void>
}

export class AuthError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}
