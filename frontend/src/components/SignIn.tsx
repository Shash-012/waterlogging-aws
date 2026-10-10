import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/context'
import type { SignInStep } from '../auth/types'

type Pending = Extract<SignInStep, { kind: 'newPasswordRequired' }>

export function SignIn() {
  const { client, setSession } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const onSignIn = (e: FormEvent) => {
    e.preventDefault()
    run(async () => {
      const step = await client.signIn(username, password)
      if (step.kind === 'signedIn') setSession(step.session)
      else {
        setPending(step)
        setPassword('')
      }
    })
  }

  const onNewPassword = (e: FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirm) {
      setError("The two passwords don't match.")
      return
    }
    run(async () => setSession(await client.completeNewPassword(pending!, newPassword)))
  }

  return (
    <main className="wl-signin">
      <div className="wl-signin-card">
        <h1>Delhi Waterlogging Early Warning</h1>
        <p className="wl-hint">For flood control room officials. Accounts are created by an admin.</p>

        {client.kind === 'demo' && (
          <p className="wl-demo-note" role="note">
            <strong>Demo sign-in.</strong> No real login is connected yet, so any username and password work. A
            username starting with "new" shows the first-sign-in step.
          </p>
        )}

        {!pending ? (
          <form onSubmit={onSignIn} aria-label="Sign in">
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="wl-primary" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        ) : (
          <form onSubmit={onNewPassword} aria-label="Choose a new password">
            <p>
              Welcome, <strong>{pending.username}</strong>. This is your first sign-in, so choose a new password.
            </p>
            <label>
              New password
              <input
                name="new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoFocus
              />
            </label>
            <label>
              Confirm new password
              <input
                name="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="wl-primary" disabled={busy}>
              {busy ? 'Saving…' : 'Set password and sign in'}
            </button>
            <button
              type="button"
              className="wl-link"
              onClick={() => {
                setPending(null)
                setError(null)
              }}
            >
              Back
            </button>
          </form>
        )}

        {error && (
          <p role="alert" className="wl-error">
            {error}
          </p>
        )}
      </div>
    </main>
  )
}
