// Mapeo slug ES -> slug EN
export const routeMap: Record<string, string> = {
	'/': '/',
	'/manifiesto': '/manifiesto',
	'/recursos': '/recursos',
	'/extranjeria': '/extranjeria',
	'/sobre-mi': '/about',
	'/contacto': '/contact',
}

// Mapeo inverso EN -> ES (se genera automáticamente)
export const reverseRouteMap: Record<string, string> = Object.fromEntries(
	Object.entries(routeMap).map(([es, en]) => [en, es])
)

export function getEquivalentPath(pathname: string): {
	es: string
	en: string
} {
	// Quita barra final salvo si es "/"
	const clean = pathname.replace(/\/$/, '') || '/'

	if (clean.startsWith('/en')) {
		const enPath = clean.replace(/^\/en/, '') || '/'
		const esPath = reverseRouteMap[enPath] ?? enPath
		return { es: esPath, en: `/en${enPath}` }
	}

	const enPath = routeMap[clean] ?? clean
	return { es: clean, en: `/en${enPath === '/' ? '' : enPath}` }
}
