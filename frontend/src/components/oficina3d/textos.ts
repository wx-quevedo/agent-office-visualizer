// All visible texts of /oficina/3d, in neutral Latin American Spanish.
// The state names come from our engine (estado.nombre); no emojis anywhere.

const TEXTOS = {
  "barra.titulo": "Oficina de agentes",
  "barra.teEsperan": "Te esperan",
  "barra.trabajando": "Trabajando",
  "barra.inactivos": "Inactivos",
  "barra.vistaCajas": "Vista de cajas",
  "barra.avisos": "Avisos",
  "barra.avisosActivos": "activos",
  "barra.avisosApagados": "apagados",
  "barra.cargando": "Cargando…",
  "barra.error": "No se pudo leer el estado; se reintenta cada 2 s.",
  "barra.ayuda":
    "Arrastra para girar · rueda o pellizco para acercar · clic en un agente para ver su detalle",
  "barra.sinAgentes": "No hay agentes abiertos.",

  "estado.idle": "Inactivo",
  "estado.thinking": "Pensando",
  "estado.working": "Trabajando",
  "estado.review": "Te espera",
  "estado.blocked": "Con errores",
  "estado.collab": "Con ayudantes",
  "estado.waiting": "Esperando",

  "burbuja.permiso": "Te pide permiso",
  "burbuja.pregunta": "Te hizo una pregunta",
  "burbuja.ayudante": "Llamó a un ayudante",
  "burbuja.segundoPlano": "En segundo plano",
  "burbuja.sinPermisos": "Sin permisos",
  ayudante: "Ayudante",

  "distintivo.error": "Error",
  "distintivo.esperaLarga": "Te espera hace rato",
  "distintivo.contexto": "Contexto lleno",
  "distintivo.pensando": "Pensando mucho",
  "distintivo.listo": "Listo",
  "distintivo.charla": "Charlando",

  "detalle.enEsteEstado": "En este estado",
  "detalle.pregunta": "Pregunta pendiente",
  "detalle.pide": "Lo que pide",
  "detalle.cuenta": "Cuenta",
  "detalle.clic": "Clic para ver el detalle",

  "pantalla.titulo": "OFICINA DE AGENTES",
} as const;

export type Clave = keyof typeof TEXTOS;

export function t(clave: Clave): string {
  return TEXTOS[clave];
}
