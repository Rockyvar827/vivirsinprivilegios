document.addEventListener('DOMContentLoaded', () => {
	const links = document.querySelectorAll<HTMLAnchorElement>('a[href]')

	links.forEach((link) => {
		const href = link.getAttribute('href')
		if (!href) return

		// Ignorar anclas, mailto, tel
		if (
			href.startsWith('#') ||
			href.startsWith('mailto:') ||
			href.startsWith('tel:')
		) {
			return
		}

		// Convertir a URL absoluta para comparar
		const url = new URL(href, window.location.origin)

		const isExternal = url.origin !== window.location.origin

		if (isExternal) {
			link.setAttribute('target', '_blank')
			link.setAttribute('rel', 'noopener noreferrer')
		}
	})
})
