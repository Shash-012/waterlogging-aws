import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/context'
import type { AuthClient, Session } from './auth/types'
import { SignIn } from './components/SignIn'

// The dashboard needs a login; the core API itself stays public and read-only.
function Gate() {
  const { session } = useAuth()
  return session ? <App /> : <SignIn />
}

export default function Root(props: { client?: AuthClient; initialSession?: Session | null }) {
  return (
    <AuthProvider {...props}>
      <Gate />
    </AuthProvider>
  )
}
