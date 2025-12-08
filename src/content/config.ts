import { defineCollection, z } from 'astro:content'

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

const recursosCollection = defineCollection({
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

export const collections = {
	blog,
	recursos: recursosCollection,
	extranjeria: extranjeriaCollection,
	about: aboutCollection,
	contact: contact,
	manifiesto: manifiestoCollection,
}
