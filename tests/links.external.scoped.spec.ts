import { test, expect } from '@playwright/test'

const START_PATHS = ['/recursos', '/extranjeria']

const PROTECTED_DOMAINS = [
	'linkedin.com',
	'sede.administracionespublicas.gob.es',
	'icp.administracionelectronica.gob.es',
	'interior.gob.es',
	'proteccion-asilo.interior.gob.es',
	'inclusion.gob.es',
]

const visited = new Set<string>()
const toVisit: string[] = [...START_PATHS]

const NON_VERIFIABLE_DYNAMIC_ENDPOINTS = [
	'sede.administracionespublicas.gob.es/tasasPDF/',
]

const protectedLinksSeen = new Set<string>()

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

				if (PROTECTED_DOMAINS.includes(hostname)) {
					protectedLinksSeen.add(link)
					console.warn(`ℹ️ Dominio protegido (no verificable por bot): ${link}`)
					continue
				}

				if (NON_VERIFIABLE_DYNAMIC_ENDPOINTS.some((p) => link.includes(p))) {
					protectedLinksSeen.add(link)
					console.warn(`ℹ️ Enlace dinámico institucional (aceptado): ${link}`)
					continue
				}

				// 🌍 Enlaces externos normales (únicos que se testean con GET)
				try {
					const response = await request.get(link, {
						timeout: 15_000,
						failOnStatusCode: false,
					})

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

					// ⚠️ Errores TLS aceptables
					if (message.includes('CERT') || message.includes('SSL')) {
						console.warn(`⚠️ Error TLS aceptado: ${link}`)
						continue
					}

					// ❌ Cualquier otro error real
					throw new Error(
						`Enlace externo inaccesible (error de red): ${link}\n${message}`
					)
				}

				if (protectedLinksSeen.size > 0) {
					console.log('\n📌 Enlaces en dominios protegidos / no verificables')
					console.log('Revisión manual recomendada:\n')

					protectedLinksSeen.forEach((link) => {
						console.log(`- ${link}`)
					})

					console.log(
						`\nTotal: ${protectedLinksSeen.size} enlace(s) a revisar manualmente.\n`
					)
				}
			}
		}
	}
})
