// All visible texts of /oficina/3d, in neutral Latin American Spanish.
// The state names come from our engine (estado.nombre); no emojis anywhere.

const TEXTOS = {
  "barra.titulo": "Oficina de agentes",
  "barra.teEsperan": "Te esperan",
  "barra.trabajando": "Trabajando",
  "barra.libres": "Libres",
  "barra.vistaCajas": "Vista de cajas",
  "barra.avisos": "Avisos",
  "barra.permisos": "Permisos",
  "permiso.cerrar": "Cerrar",
  "permiso.detalle": "Ver detalle completo",
  "panel.noEsta": "Ese agente ya no está en la oficina",
  "permiso.vscode": "Responde en VS Code.",
  "barra.avisosActivos": "activos",
  "barra.avisosApagados": "apagados",
  "barra.cargando": "Cargando…",
  "barra.error": "No se pudo leer el estado; se reintenta cada 2 s.",
  "barra.ayuda":
    "Arrastra para girar · rueda o pellizco para acercar · clic en un agente para ver su detalle",
  "barra.sinAgentes": "No hay agentes abiertos.",

  "burbuja.ayudante": "Llamó a un ayudante",
  ayudante: "Ayudante",

  "distintivo.error": "Error",
  "distintivo.esperaLarga": "Te espera hace rato",
  "distintivo.contexto": "Contexto lleno",
  "distintivo.pensando": "Pensando mucho",
  "distintivo.listo": "Listo",
  "distintivo.charla": "Charlando",
  "distintivo.conErrores": "Con errores",

  "nota.cerrado":
    "Se cerró con esta pregunta pendiente; la nota se queda hasta que reabras la sesión.",

  "detalle.enEsteEstado": "En este estado",
  "detalle.pregunta": "Pregunta pendiente",
  "detalle.pide": "Lo que pide",
  "detalle.cuenta": "Cuenta",
  "detalle.clic": "Clic para ver su panel",

  "pantalla.titulo": "OFICINA DE AGENTES",
  "pantalla.nadie": "nadie",
  "tuPuesto.letrero": "Tú",
  "grupo.cabinaGeneral": "Cabina general",
  "grupo.islaGeneral": "Isla general",
  "barra.entorno": "Entorno",

  "barra.editar": "Editar oficina",
  "editor.titulo": "Editar oficina",
  "editor.ayuda":
    "Elige un mueble y haz clic en el piso para agregarlo. Arrastra un mueble para moverlo (cuadrícula de 0,5 m).",
  "editor.muebles": "Muebles",
  "editor.seleccionado": "Mueble seleccionado",
  "editor.ninguno": "Ninguno: haz clic en un mueble.",
  "editor.rotar": "Rotar",
  "editor.borrar": "Borrar",
  "editor.deshacer": "Deshacer",
  "editor.rehacer": "Rehacer",
  "editor.tema": "Tema de piso y pared",
  "editor.guardar": "Guardar",
  "editor.guardando": "Guardando…",
  "editor.cancelar": "Cancelar",
  "editor.exportar": "Exportar JSON",
  "editor.importar": "Importar JSON",
  "editor.importarError": "El archivo no es una distribución válida.",
  "editor.tapaCamino": "tapa un camino de los agentes",
  "editor.tapaEscritorio": "tapa un escritorio de trabajo",
  "editor.avisoBloqueo": "Mueve estos muebles para poder guardar:",
  "editor.cantidad": "muebles agregados",
  "editor.atajos":
    "Atajos: R rota, Supr borra, Ctrl+Z deshace, Ctrl+Y rehace, Esc suelta el mueble elegido.",
} as const;

export type Clave = keyof typeof TEXTOS;

export function t(clave: Clave): string {
  return TEXTOS[clave];
}
