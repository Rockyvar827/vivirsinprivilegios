export const NOMBRE_SITIO = "Vivir sin privilegios"; // ajusta si el nombre es otro

export const CATEGORIAS = {
  nacionalidad: {
    nombre: "Nacionalidad",
    descripcion: "Cambios en los requisitos y trámites para obtener la nacionalidad española.",
  },
  residencia: {
    nombre: "Residencia",
    descripcion: "Novedades sobre autorizaciones de residencia, arraigo, reagrupación familiar y visados.",
  },
  asilo: {
    nombre: "Asilo y protección internacional",
    descripcion: "Novedades sobre solicitudes de asilo, refugio y protección internacional en España.",
  },
  estudiantes: {
    nombre: "Estudiantes",
    descripcion: "Cambios que afectan a estudiantes extranjeros: estancia, prórrogas y paso a residencia.",
  },
  legislacion: {
    nombre: "Legislación",
    descripcion: "Leyes, reglamentos y órdenes que modifican la normativa de extranjería.",
  },
  otros: {
    nombre: "Otras novedades",
    descripcion: "Otras novedades oficiales relacionadas con la extranjería.",
  },
} as const;

export type Categoria = keyof typeof CATEGORIAS;

export const fechaLarga = (d: Date) =>
  d.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export const fechaISO = (d: Date) => d.toISOString().slice(0, 10);

// Categorías que tienen al menos una novedad publicada, con su recuento
export function resumenCategorias(novedades: { data: { category: Categoria } }[]) {
  return (Object.keys(CATEGORIAS) as Categoria[])
    .map((slug) => ({
      slug,
      nombre: CATEGORIAS[slug].nombre,
      total: novedades.filter((n) => n.data.category === slug).length,
    }))
    .filter((c) => c.total > 0);
}

// Evita que un "<" dentro del JSON rompa el script
export const jsonSeguro = (obj: unknown) => JSON.stringify(obj).replace(/</g, "\\u003c");