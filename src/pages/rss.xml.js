import { getCollection } from 'astro:content'
import { SITE_TITLE, SITE_DESCRIPTION } from '../consts'

// Feed RSS 2.0 generado a mano, sin depender de @astrojs/rss
// (la versión actual de ese paquete no es compatible con Astro 6 / Zod 4).

const escapar = (texto) =>
	String(texto)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&apos;')

export async function GET(context) {
	const site = context.site ?? new URL('https://www.vivirsinprivilegios.org')

	const posts = (await getCollection('blog')).sort(
		(a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
	)

	const items = posts
		.map((post) => {
			const enlace = new URL(`/blog/${post.id}/`, site).href
			return `    <item>
      <title>${escapar(post.data.title)}</title>
      <link>${enlace}</link>
      <guid isPermaLink="true">${enlace}</guid>
      <pubDate>${post.data.pubDate.toUTCString()}</pubDate>
      <description>${escapar(post.data.description)}</description>
    </item>`
		})
		.join('\n')

	// La fecha del último cambio es la del post más reciente (así el feed es estable entre builds)
	const ultima = posts.length ? posts[0].data.pubDate.toUTCString() : new Date(0).toUTCString()

	const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapar(SITE_TITLE)}</title>
    <link>${site.href}</link>
    <description>${escapar(SITE_DESCRIPTION)}</description>
    <language>es</language>
    <lastBuildDate>${ultima}</lastBuildDate>
    <atom:link href="${new URL('/rss.xml', site).href}" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>
`

	return new Response(xml, {
		headers: { 'Content-Type': 'application/xml; charset=utf-8' },
	})
}