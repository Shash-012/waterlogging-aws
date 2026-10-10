import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Root from '../Root'
import { authFromEnv, createCognitoAuth } from './cognito'
import { demoAuth } from './demo'
import { isExpired, loadSession, saveSession, sessionFromIdToken } from './session'

function jwt(claims: object): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'RS256' })}.${b64(claims)}.sig`
}

const inAnHour = () => Math.floor(Date.now() / 1000) + 3600

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

describe('sign-in screen (demo login)', () => {
  it('gates the dashboard, signs in and signs out', async () => {
    render(<Root client={demoAuth} initialSession={null} />)
    expect(screen.getByRole('note')).toHaveTextContent('Demo sign-in')
    expect(screen.queryByText(/hotspots/)).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'officer' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'anything' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('officer')).toBeInTheDocument()
    expect(await screen.findByText(/12 hotspots/)).toBeInTheDocument()
    // The session survives a reload of this tab.
    expect(loadSession()?.username).toBe('officer')

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(loadSession()).toBeNull()
  })

  it('walks a first sign-in through choosing a new password', async () => {
    render(<Root client={demoAuth} initialSession={null} />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'new-officer' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Temp#1234' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText(/first sign-in/)).toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Set password and sign in' })

    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'Abcdef#12' } })
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'different' } })
    fireEvent.click(submit)
    expect(screen.getByRole('alert')).toHaveTextContent("don't match")

    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'short' } })
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'short' } })
    fireEvent.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters')

    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'Abcdef#12' } })
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'Abcdef#12' } })
    fireEvent.click(submit)
    expect(await screen.findByText(/12 hotspots/)).toBeInTheDocument()
    expect(screen.getByText(/Signed in as/)).toHaveTextContent('Signed in as new-officer')
  })

  it('starts on the sign-in screen when the stored session has expired', () => {
    saveSession({ username: 'old', idToken: 'x', expiresAt: Date.now() - 1000 })
    render(<Root client={demoAuth} />)
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})

describe('Cognito client', () => {
  const config = { userPoolId: 'ap-south-1_AbC123', clientId: 'client-123' }

  function mockFetch(...responses: Array<{ status?: number; body: object }>) {
    const fetchMock = vi.fn()
    for (const r of responses) {
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(r.body), { status: r.status ?? 200 }))
    }
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('signs in with USER_PASSWORD_AUTH against the pool region', async () => {
    const fetchMock = mockFetch({
      body: { AuthenticationResult: { IdToken: jwt({ 'cognito:username': 'officer', exp: inAnHour() }) } },
    })
    const step = await createCognitoAuth(config).signIn(' officer ', 'pw')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://cognito-idp.ap-south-1.amazonaws.com/')
    expect(init.headers['X-Amz-Target']).toBe('AWSCognitoIdentityProviderService.InitiateAuth')
    expect(JSON.parse(init.body)).toEqual({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: 'client-123',
      AuthParameters: { USERNAME: 'officer', PASSWORD: 'pw' },
    })
    expect(step.kind === 'signedIn' && step.session.username).toBe('officer')
  })

  it('handles NEW_PASSWORD_REQUIRED for admin-created users', async () => {
    const fetchMock = mockFetch(
      { body: { ChallengeName: 'NEW_PASSWORD_REQUIRED', Session: 'sess-1' } },
      { body: { AuthenticationResult: { IdToken: jwt({ 'cognito:username': 'officer', exp: inAnHour() }) } } },
    )
    const auth = createCognitoAuth(config)
    const step = await auth.signIn('officer', 'Temp#1234')
    expect(step).toEqual({ kind: 'newPasswordRequired', username: 'officer', challenge: 'sess-1' })

    const session = await auth.completeNewPassword(step as Extract<typeof step, { kind: 'newPasswordRequired' }>, 'New#Pass123')
    expect(session.username).toBe('officer')
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      ChallengeName: 'NEW_PASSWORD_REQUIRED',
      ClientId: 'client-123',
      Session: 'sess-1',
      ChallengeResponses: { USERNAME: 'officer', NEW_PASSWORD: 'New#Pass123' },
    })
  })

  it('turns Cognito errors into plain messages', async () => {
    mockFetch({ status: 400, body: { __type: 'NotAuthorizedException', message: 'Incorrect username or password.' } })
    await expect(createCognitoAuth(config).signIn('officer', 'bad')).rejects.toThrow('Wrong username or password.')
  })

  it('is used only when both Cognito settings are present', () => {
    expect(authFromEnv({} as ImportMetaEnv)).toBeNull()
    expect(authFromEnv({ VITE_COGNITO_USER_POOL_ID: 'ap-south-1_x' } as ImportMetaEnv)).toBeNull()
    expect(
      authFromEnv({ VITE_COGNITO_USER_POOL_ID: 'ap-south-1_x', VITE_COGNITO_CLIENT_ID: 'c' } as ImportMetaEnv)?.kind,
    ).toBe('cognito')
  })
})

describe('session', () => {
  it('reads username and expiry from the id token', () => {
    const exp = inAnHour()
    const s = sessionFromIdToken(jwt({ 'cognito:username': 'officer', exp }), 'fallback')
    expect(s).toEqual({ username: 'officer', idToken: expect.any(String), expiresAt: exp * 1000 })
    expect(isExpired(s)).toBe(false)
    expect(isExpired({ ...s, expiresAt: Date.now() + 30_000 })).toBe(true)
  })
})
