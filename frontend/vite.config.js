import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-server only. The proxy target is where `npm run dev` forwards /api calls;
// it has nothing to do with production, where /api is served same-origin by a
// reverse proxy (or overridden with VITE_API_BASE_URL at build time).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_DEV_PORT) || 3000,
      proxy: {
        '/api': env.VITE_DEV_API_PROXY || 'http://localhost:8000',
      },
    },
  }
})
