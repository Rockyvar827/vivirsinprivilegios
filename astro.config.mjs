import { defineConfig } from 'astro/config'
import tailwindcss from '@tailwindcss/vite'
import mdx from '@astrojs/mdx'
import sitemap from '@astrojs/sitemap'
import partytown from '@astrojs/partytown'
import icon from 'astro-icon'
import rehypeExternalLinks from 'rehype-external-links'

// https://astro.build/config
export default defineConfig({
	site: 'https://www.vivirsinprivilegios.org',
	integrations: [
		mdx(),
		sitemap(),
		icon(),
		partytown({
			config: {
				forward: ['dataLayer.push'],
			},
		}),
	],
	vite: {
		plugins: [tailwindcss()],
	},
	markdown: {
		rehypePlugins: [
			[
				rehypeExternalLinks,
				{
					target: '_blank',
					rel: ['noopener', 'noreferrer'],
				},
			],
		],
	},
})