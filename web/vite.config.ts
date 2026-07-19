import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 백엔드가 `/app` 아래에서 정적 서빙하므로 빌드 산출물의 asset 경로를 맞춘다.
// 개발 서버(`npm run dev`)에서는 실제 디바이스(UNO Q) HTTP 서버로 /stats.json,
// /stream.mjpg, /api/* 를 프록시해 CORS 없이 로컬에서 바로 개발할 수 있게 한다.
const DEV_BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8080'

export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    proxy: {
      '/stats.json': DEV_BACKEND,
      '/stream.mjpg': DEV_BACKEND,
      '/api': DEV_BACKEND,
    },
  },
})
