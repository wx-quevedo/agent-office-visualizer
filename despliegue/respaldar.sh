#!/usr/bin/env bash
# Respaldo de las bases de la oficina (lo corre el timer diario como el usuario
# del servicio; también a mano: sudo -u visualizador bash respaldar.sh).
#
# Copia consistente de cada base SQLite con la API de respaldo (sirve con el
# backend en marcha y en modo WAL), comprueba su integridad, agrega los JSON
# (configuración de permisos, distribución) y deja un .tar.gz por día en
# /var/lib/visualizador-agentes/respaldos. Conserva 14 días.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
# El usuario del servicio no puede entrar al directorio de quien lo llama
# (por ejemplo /home/<VPS_USER>): todo corre desde la raíz.
cd /

ORIGEN="${1:-$DATOS}"
DESTINO="${2:-$RESPALDOS}"
DIAS=14
umask 077
sello="$(date -u +%Y%m%d-%H%M%S)"
tmp="$DESTINO/.en-curso-$sello"
mkdir -p "$tmp"
trap 'rm -rf "$tmp" "$DESTINO"/respaldo-*.tar.gz.tmp' EXIT

python3 -I - "$ORIGEN" "$tmp" <<'PY'
import shutil
import sqlite3
import sys
from pathlib import Path

origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
total = 0
for f in sorted(origen.rglob("*")):
    if not f.is_file():
        continue
    rel = f.relative_to(origen)
    if f.suffix == ".db":
        d = destino / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        src, dst = sqlite3.connect(f), sqlite3.connect(d)
        try:
            src.backup(dst)
            ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            src.close()
            dst.close()
        if ok != "ok":
            sys.exit(f"Integridad fallida en {rel}: {ok}")
        total += 1
    elif f.suffix == ".json":
        d = destino / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
print(f"{total} bases copiadas")
PY

archivo="$DESTINO/respaldo-$sello.tar.gz"
tar -czf "$archivo.tmp" -C "$tmp" .
mv "$archivo.tmp" "$archivo"
find "$DESTINO" -maxdepth 1 -name 'respaldo-*.tar.gz' -mtime +"$((DIAS - 1))" -delete

# Estado legible por <VPS_USER> (estado.sh), sin datos.
if [ "$DESTINO" = "$RESPALDOS" ]; then
  {
    echo "ultimo=$(basename "$archivo")"
    echo "tamano=$(du -h "$archivo" | cut -f1)"
    echo "cantidad=$(find "$DESTINO" -maxdepth 1 -name 'respaldo-*.tar.gz' | wc -l)"
    echo "hora=$(date -u +%FT%TZ)"
  } > "$DATOS_RAIZ/estado-respaldo.txt"
  chmod 644 "$DATOS_RAIZ/estado-respaldo.txt"
fi
echo "Respaldo: $archivo"
