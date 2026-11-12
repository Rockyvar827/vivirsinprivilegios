import type { CollectionEntry } from "astro:content";

export const CATEGORIAS_EXTRANJERIA = {
  documentacion: { slug: "documentacion", nombre: "Citas y documentación" },
  residencia: { slug: "residencia", nombre: "Residencia y arraigo" },
  asilo: { slug: "asilo", nombre: "Asilo y protección" },
  reclamaciones: { slug: "reclamaciones", nombre: "Reclamaciones y recursos" },
  galicia: { slug: "galicia", nombre: "Ayuda en Galicia" },
} as const;

export function resumenCategoriasExtranjeria(posts: CollectionEntry<"extranjeria">[]) {
  return Object.values(CATEGORIAS_EXTRANJERIA)
    .map((cat) => ({
      ...cat,
      total: posts.filter((p) => p.data.category === cat.slug).length,
    }))
    .filter((cat) => cat.total > 0);
}