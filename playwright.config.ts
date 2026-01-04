import { defineConfig } from '@playwright/test'

export default defineConfig({
	testDir: './tests',
	timeout: 30_000,
	retries: process.env.CI ? 2 : 0,
	use: {
		baseURL: 'http://localhost:4321', // Astro dev / preview
		headless: true,
	},
	webServer: {
		command: 'npm run preview', // o `astro preview`
		port: 4321,
		reuseExistingServer: !process.env.CI,
	},
})
