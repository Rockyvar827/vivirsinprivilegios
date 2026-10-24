import { defineCollection, z } from 'astro:content'
import { glob } from 'astro/loaders'

// Cada colección carga sus ficheros con un `loader` (obligatorio en Astro 6).
// Las carpetas deben llamarse igual que la colección: src/content/<nombre>/
const cargar = (nombre: string) =>
	glob({ pattern: '**/*.{md,mdx}', base: `./src/content/${nombre}` })

// Esquema compartido por las páginas sueltas (about, manifiesto, cookies, privacy)
const paginaSchema = z.object({
	title: z.string(),
	description: z.string(),
	author: z.string().optional(),
	pubDate: z.coerce.date().optional(),
	image: z
		.object({
			url: z.string(),
			alt: z.string().optional(),
		})
		.optional(),
})

const blog = defineCollection({
	loader: cargar('blog'),
	schema: z.object({
		title: z.string(),
		description: z.string(),
		pubDate: z.coerce.date(),
		updatedDate: z.coerce.date().optional(),
		coverImageCredit: z.string().optional(),
		seoTitle: z.string().optional(),
	}),
})

const extranjeria = defineCollection({
	loader: cargar('extranjeria'),
	schema: z.object({
	title: z.string(),
	seoTitle: z.string().optional(),
	description: z.string(),
	pubDate: z.coerce.date(),
	category: z.string().optional(),
		tags: z.array(z.string()).optional(),
	}),
})

const about = defineCollection({ loader: cargar('about'), schema: paginaSchema })
const manifiesto = defineCollection({ loader: cargar('manifiesto'), schema: paginaSchema })
const cookies = defineCollection({ loader: cargar('cookies'), schema: paginaSchema })
const privacy = defineCollection({ loader: cargar('privacy'), schema: paginaSchema })

const contact = defineCollection({
	loader: cargar('contact'),
	schema: z.object({
		title: z.string(),
		description: z.string().optional(),
		email: z.string().optional(),
		emailText: z.string().optional(),
		socialProfiles: z
			.array(
				z.object({
					text: z.string(),
					href: z.string().url(),
				})
			)
			.optional(),
	}),
})

const novedades = defineCollection({
	loader: glob({ pattern: '**/*.md', base: './src/content/novedades' }),
	schema: z.object({
		title: z.string(),
		description: z.string(),
		pubDate: z.coerce.date(),
		checkedDate: z.coerce.date(),
		source: z.string(),
		sourceUrl: z.string().url(),
		category: z.enum([
			'nacionalidad',
			'residencia',
			'asilo',
			'estudiantes',
			'legislacion',
			'otros',
		]),
		draft: z.boolean().default(false),
	}),
})

export const collections = {
	blog,
	extranjeria,
	about,
	contact,
	manifiesto,
	cookies,
	privacy,
	novedades,
}