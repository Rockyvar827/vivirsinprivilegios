import { test, expect } from '@playwright/test'

const visited = new Set<string>()
const toVisit: string[] = ['/']

test('no existen enlaces rotos en la web', async ({
	page,
	request,
	baseURL,
}) => {
	if (!baseURL) throw new Error('baseURL no definido')

	while (toVisit.length > 0) {
		const path = toVisit.pop()!
		if (visited.has(path)) continue

		visited.add(path)

		const response = await request.get(path)
		expect(
			response.ok(),
			`Enlace roto detectado: ${path} → ${response.status()}`
		).toBeTruthy()

		await page.goto(path)

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

			// Enlaces internos
			if (link.startsWith('/')) {
				if (!visited.has(link)) {
					toVisit.push(link)
				}
			}
		}
	}
})
