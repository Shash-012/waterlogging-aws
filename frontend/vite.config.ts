/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The fixtures live in ../contract/fixtures, outside this folder.
  server: { fs: { allow: ['..'] } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Tests always run on fixtures and the demo login, whatever .env.local says,
    // so they never call the live APIs or Cognito.
    env: {
      VITE_DATA_SOURCE: 'fixtures',
      VITE_CORE_API_URL: '',
      VITE_OPS_API_URL: '',
      VITE_COGNITO_USER_POOL_ID: '',
      VITE_COGNITO_CLIENT_ID: '',
    },
  },
})
