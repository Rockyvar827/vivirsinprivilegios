import type { CollectionEntry } from "astro:content";

export const CATEGORIAS_BLOG = {
  burocracia: { slug: "burocracia", nombre: "Burocracia y migración" },
  racismo: { slug: "racismo", nombre: "Antirracismo" },
  feminismo: { slug: "feminismo", nombre: "Feminismo" },
  trabajo: { slug: "trabajo", nombre: "Trabajo y mobbing" },
  universidad: { slug: "universidad", nombre: "Universidad" },
} as const;

export function resumenCategoriasBlog(posts: CollectionEntry<"blog">[]) {
  return Object.values(CATEGORIAS_BLOG)
    .map((cat) => ({
      ...cat,
      total: posts.filter((p) => p.data.category === cat.slug).length,
    }))
    .filter((cat) => cat.total > 0);
}