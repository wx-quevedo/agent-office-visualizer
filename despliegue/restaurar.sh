#!/usr/bin/env bash
# Restaura un respaldo de la oficina.
#
#   Prueba en una copia (no toca nada en uso):
#     sudo -u visualizador bash restaurar.sh --copia /var/lib/visualizador-agentes/respaldos/respaldo-AAAAMMDD-HHMMSS.tar.gz
#
#   Restauración real (detiene el backend, guarda los datos actuales en
#   datos.antes-<fecha>, restaura y vuelve a arrancar):
#     sudo bash restaurar.sh /var/lib/visualizador-agentes/respaldos/respaldo-AAAAMMDD-HHMMSS.tar.gz
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
# El usuario del servicio no puede entrar al directorio de quien lo llama
# (por ejemplo /home/<VPS_USER>): todo corre desde la raíz.
cd /

COPIA=""
if [ "${1:-}" = "--copia" ]; then COPIA=1; shift; fi
ARCHIVO="${1:?falta el archivo del respaldo}"
[ -f "$ARCHIVO" ] || { echo "No existe $ARCHIVO"; exit 1; }

comprobar() {
  python3 -I - "$1" <<'PY'
import sqlite3
import sys
from pathlib import Path

for f in sorted(Path(sys.argv[1]).rglob("*.db")):
    db = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
    try:
        ok = db.execute("PRAGMA integrity_check").fetchone()[0]
        tablas = [t for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        filas = sum(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas)
    finally:
        db.close()
    print(f"  {f.name}: integridad {ok}, {len(tablas)} tablas, {filas} filas")
    if ok != "ok":
        sys.exit(1)
PY
}

if [ -n "$COPIA" ]; then
  umask 077
  copia="$DATOS_RAIZ/prueba-restauracion-$(date -u +%Y%m%d-%H%M%S)"
  mkdir -p "$copia"
  tar -xzf "$ARCHIVO" -C "$copia"
  echo "Restaurado en la copia $copia:"
  comprobar "$copia"
  rm -rf "$copia"
  echo "Prueba de restauración correcta (copia borrada)."
  exit 0
fi

[ "$(id -u)" = 0 ] || { echo "La restauración real se ejecuta con sudo."; exit 1; }
sano() {
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}
nuevo="$DATOS_RAIZ/datos.restaurando"
rm -rf "$nuevo"
install -d -o "$USUARIO_SERVICIO" -g "$USUARIO_SERVICIO" -m 700 "$nuevo"
# Se extrae y se comprueba como el usuario del servicio, no como root.
sudo -u "$USUARIO_SERVICIO" tar --no-same-owner -xzf "$ARCHIVO" -C "$nuevo"
echo "Comprobando el respaldo:"
sudo -u "$USUARIO_SERVICIO" bash -c "cd / && $(declare -f comprobar); comprobar '$nuevo'"
systemctl stop "$SERVICIO"
sello="$(date -u +%Y%m%d-%H%M%S)"
antes="$DATOS_RAIZ/datos.antes-$sello"
mv "$DATOS" "$antes"
mv "$nuevo" "$DATOS"
systemctl start "$SERVICIO"
if sano; then
  echo "Restaurado. Los datos anteriores quedaron en $antes"
  exit 0
fi
echo "El backend no respondió con el respaldo: se vuelve a los datos anteriores."
systemctl stop "$SERVICIO"
mv "$DATOS" "$DATOS_RAIZ/datos.fallido-$sello"
mv "$antes" "$DATOS"
systemctl start "$SERVICIO"
if sano; then
  echo "Se volvió a los datos anteriores; el respaldo quedó en $DATOS_RAIZ/datos.fallido-$sello"
else
  echo "El backend tampoco responde con los datos anteriores: revisar journalctl -u $SERVICIO"
fi
exit 1
