/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // jsdom simula el DOM en Node -sin esto, testing-library no tiene dónde
    // montar un componente: no hay navegador real corriendo en CI.
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
