// Después de `next build` (export estático): Next 16 escribe las cargas RSC de
// cada segmento en carpetas (`oficina/3d/__next.oficina/3d/__PAGE__.txt`), pero
// el cliente las pide con puntos (`oficina/3d/__next.oficina.3d.__PAGE__.txt`)
// al precargar un enlace o al cambiar la URL con router.replace. Sin el archivo
// plano, el servidor responde 404 y Next recarga la página entera. Este paso
// copia cada archivo con el nombre que pide el cliente.
import { copyFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const OUT = new URL("../out/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? archivos(p) : [p];
  });
}

if (!existsSync(OUT)) {
  console.error(`No existe ${OUT}: ejecutar después de next build.`);
  process.exit(1);
}
let copiados = 0;
for (const f of archivos(OUT)) {
  const partes = relative(OUT, f).split(sep);
  const i = partes.findIndex((p) => p.startsWith("__next.") && !p.endsWith(".txt"));
  if (i < 0) continue;
  const plano = [...partes.slice(0, i), partes.slice(i).join(".")];
  const destino = join(OUT, ...plano);
  if (!existsSync(destino)) {
    copyFileSync(f, destino);
    copiados++;
  }
}
console.log(`rsc-planos: ${copiados} archivos con el nombre plano que pide el cliente`);
