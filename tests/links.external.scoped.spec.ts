import { test, expect } from '@playwright/test'

const START_PATHS = ['/recursos', '/extranjeria']

const PROTECTED_DOMAINS = ['linkedin.com']
const ACCEPTED_PROTECTED_STATUS = [200, 301, 302, 401, 403, 999]

const visited = new Set<string>()
const toVisit: string[] = [...START_PATHS]

test('enlaces externos válidos en /recursos y /extranjeria (detecta DNS)', async ({
	page,
	request,
	baseURL,
}) => {
	if (!baseURL) throw new Error('baseURL no definido')

	while (toVisit.length > 0) {
		const path = toVisit.pop()!
		if (visited.has(path)) continue

		visited.add(path)

		// Cargar la ruta interna
		await page.goto(path, { waitUntil: 'load' })

		// Extraer todos los href
		const links = await page.$$eval('a[href]', (anchors) =>
			anchors.map((a) => a.getAttribute('href')).filter(Boolean)
		)

		for (const link of links) {
			if (!link) continue

			// Ignorar anclas, mailto, tel
			if (
				link.startsWith('#') ||
				link.startsWith('mailto:') ||
				link.startsWith('tel:')
			) {
				continue
			}

			// 🔁 Rutas internas a seguir (solo /recursos y /extranjeria)
			if (
				link.startsWith('/') &&
				(link.startsWith('/recursos') || link.startsWith('/extranjeria'))
			) {
				if (!visited.has(link)) {
					toVisit.push(link)
				}
				continue
			}

			// 🌐 Enlaces externos
			if (link.startsWith('http')) {
				const hostname = new URL(link).hostname.replace('www.', '')

				try {
					const response = await request.get(link, {
						timeout: 15_000,
						failOnStatusCode: false,
					})

					// LinkedIn: dominio protegido
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
					const message = error.message || ''

					// 🚨 NXDOMAIN → fallo obligatorio
					if (
						message.includes('ERR_NAME_NOT_RESOLVED') ||
						message.includes('NXDOMAIN')
					) {
						throw new Error(
							`🚨 NXDOMAIN detectado: dominio inexistente\n${link}`
						)
					}

					// ⚠️ Errores TLS aceptables (web accesible en navegador)
					if (
						message.includes('unable to verify the first certificate') ||
						message.includes('Hostname/IP does not match certificate') ||
						message.includes('CERT') ||
						message.includes('SSL')
					) {
						console.warn(
							`⚠️ Certificado TLS no compatible (se acepta): ${link}`
						)
						continue
					}

					// ❌ Cualquier otro error de red
					throw new Error(
						`Enlace externo inaccesible (error de red): ${link}\n${message}`
					)
				}
			}
		}
	}
})
