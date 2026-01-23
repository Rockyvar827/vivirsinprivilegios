document.addEventListener('DOMContentLoaded', () => {
	const anchors =
		document.querySelectorAll<HTMLAnchorElement>('a[href^="http"]')

	anchors.forEach((a) => {
		const url = new URL(a.href)

		if (url.hostname !== window.location.hostname) {
			a.target = '_blank'
			a.rel = 'noopener noreferrer'
		}
	})
})
