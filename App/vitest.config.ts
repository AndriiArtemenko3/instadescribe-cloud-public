// Vitest picks this file over vite.config.ts. It reuses the app's Vite
// config and adds the storage polyfill setup for the node test environment.
import { mergeConfig } from 'vite'
import { defineConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      setupFiles: ['./src/test/setup.ts'],
    },
  }),
)
