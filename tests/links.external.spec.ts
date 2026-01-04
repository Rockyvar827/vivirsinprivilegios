import { test, expect } from '@playwright/test'

const PROTECTED_DOMAINS = ['linkedin.com']
const ACCEPTED_PROTECTED_STATUS = [200, 301, 302, 401, 403, 999]

test('los enlaces externos son accesibles (detecta DNS)', async ({
	page,
	request,
	baseURL,
}) => {
	if (!baseURL) throw new Error('baseURL no definido')

	await page.goto('/')

	const externalLinks = await page.$$eval('a[href]', (anchors) =>
		Array.from(
			new Set(
				anchors
					.map((a) => a.getAttribute('href'))
					.filter(
						(href) =>
							href &&
							href.startsWith('http') &&
							!href.startsWith('mailto:') &&
							!href.startsWith('tel:')
					)
			)
		)
	)

	for (const link of externalLinks) {
		if (!link) continue
		const hostname = new URL(link).hostname.replace('www.', '')

		try {
			const response = await request.get(link, {
				timeout: 15_000,
				failOnStatusCode: false,
			})

			// LinkedIn (dominio protegido)
			if (PROTECTED_DOMAINS.includes(hostname)) {
				expect(
					ACCEPTED_PROTECTED_STATUS.includes(response.status()),
					`Enlace protegido inaccesible: ${link} → ${response.status()}`
				).toBeTruthy()
				continue
			}

			// Resto de enlaces externos
			expect(
				response.ok(),
				`Enlace externo roto: ${link} → ${response.status()}`
			).toBeTruthy()
		} catch (error: any) {
			// 🚨 AQUÍ entra NXDOMAIN y errores de red
			throw new Error(
				`Enlace externo inaccesible (error de red/DNS): ${link}\n${error.message}`
			)
		}
	}
})
