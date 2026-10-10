/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_SOURCE?: 'fixtures' | 'live'
  readonly VITE_CORE_API_URL?: string
  readonly VITE_OPS_API_URL?: string
  readonly VITE_COGNITO_USER_POOL_ID?: string
  readonly VITE_COGNITO_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
