import { defineCollection, z } from 'astro:content'
import { glob } from "astro/loaders";

const blog = defineCollection({
	// Type-check frontmatter using a schema
	schema: z.object({
		title: z.string(),
		description: z.string(),
		pubDate: z.coerce.date(),
		updatedDate: z.coerce.date().optional(),
		coverImageCredit: z.string().optional(),
	}),
})

const extranjeriaCollection = defineCollection({
	type: 'content',
	schema: z.object({
		title: z.string(),
		description: z.string(),
		pubDate: z.date(),
		category: z.string().optional(),
		tags: z.array(z.string()).optional(),
	}),
})
const aboutCollection = defineCollection({
	type: 'content',
	schema: z.object({
		title: z.string(),
		description: z.string(),
		author: z.string().optional(),
		pubDate: z.date().optional(),
		image: z
			.object({
				url: z.string(),
				alt: z.string().optional(),
			})
			.optional(),
	}),
})

const contact = defineCollection({
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

const manifiestoCollection = defineCollection({
	type: 'content',
	schema: z.object({
		title: z.string(),
		description: z.string(),
		author: z.string().optional(),
		pubDate: z.date().optional(),
		image: z
			.object({
				url: z.string(),
				alt: z.string().optional(),
			})
			.optional(),
	}),
})
const cookiesCollection = defineCollection({
	type: 'content',
	schema: z.object({
		title: z.string(),
		description: z.string(),
		author: z.string().optional(),
		pubDate: z.date().optional(),
		image: z
			.object({
				url: z.string(),
				alt: z.string().optional(),
			})
			.optional(),
	}),
})

const privacyCollection = defineCollection({
	type: 'content',
	schema: z.object({
		title: z.string(),
		description: z.string(),
		author: z.string().optional(),
		pubDate: z.date().optional(),
		image: z
			.object({
				url: z.string(),
				alt: z.string().optional(),
			})
			.optional(),
	}),
})


const novedades = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/novedades" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    checkedDate: z.coerce.date(),
    source: z.string(),
    sourceUrl: z.string().url(),
    category: z.enum(["nacionalidad", "residencia", "asilo", "estudiantes", "legislacion", "otros"]),
    draft: z.boolean().default(false),
  }),
});


export const collections = {
	blog,
	extranjeria: extranjeriaCollection,
	about: aboutCollection,
	contact: contact,
	manifiesto: manifiestoCollection,
	cookies: cookiesCollection,
	privacy: privacyCollection,
	novedades: novedades
}
