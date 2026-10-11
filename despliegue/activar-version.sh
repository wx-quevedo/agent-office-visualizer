#!/usr/bin/env bash
# Activa una versión ya subida al VPS (lo corre desplegar.sh por ssh, como <VPS_USER>,
# sin sudo):
#
#   bash /var/www/visualizador-agentes/versiones/<id>/despliegue/activar-version.sh <id>
#
# 1. Prepara uv (una vez) y Python 3.13 propio dentro de /var/www/visualizador-agentes/herramientas.
# 2. Crea el entorno del backend de esa versión (uv sync --frozen, sin dependencias de desarrollo).
# 3. Cambia el enlace "actual" de forma atómica y pide el reinicio (archivo "reiniciar",
#    que vigila la unidad visualizador-agentes-reinicio.path).
# 4. Espera /health; si no responde, vuelve a la versión anterior.
# 5. Conserva las últimas versiones y borra las demás.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"

ID="${1:?falta el id de la versión}"
# Un despliegue a la vez.
exec 9>"$RAIZ/.despliegue.lock"
flock -n 9 || { echo "Hay otro despliegue en curso."; exit 1; }
VERSION_DIR="$RAIZ/versiones/$ID"
[ -d "$VERSION_DIR/backend" ] || { echo "No existe $VERSION_DIR/backend"; exit 1; }

HERR="$RAIZ/herramientas"
UV_VERSION="0.11.32"
export UV_PYTHON_INSTALL_DIR="$HERR/python"
export UV_PYTHON_PREFERENCE=only-managed
export UV_CACHE_DIR="$HERR/cache"
export UV_NO_PROGRESS=1
UV="$HERR/uv-env/bin/uv"

if [ ! -x "$UV" ] || [ "$("$UV" --version | awk '{print $2}')" != "$UV_VERSION" ]; then
  echo "Instalando uv $UV_VERSION en $HERR/uv-env"
  python3 -m venv "$HERR/uv-env"
  "$HERR/uv-env/bin/pip" install --quiet --disable-pip-version-check "uv==$UV_VERSION"
fi

echo "Entorno del backend ($ID)"
(cd "$VERSION_DIR/backend" && "$UV" sync --frozen --no-dev --python 3.13 --quiet)
# Comprobación rápida: la aplicación importa.
(cd "$VERSION_DIR/backend" && .venv/bin/python -c "import app.main" >/dev/null)

ANTERIOR="$(readlink "$RAIZ/actual" 2>/dev/null || true)"
# Para saber que el backend de verdad se reinició (y no responde el proceso viejo).
INVOCACION="$(systemctl show "$SERVICIO" -p InvocationID --value 2>/dev/null || true)"
ln -sfn "versiones/$ID" "$RAIZ/actual.nuevo"
mv -T "$RAIZ/actual.nuevo" "$RAIZ/actual"
date -u +%FT%TZ > "$RAIZ/reiniciar"
echo "Versión activa: $ID (anterior: ${ANTERIOR:-ninguna})"

# Espera a que el backend responda con la versión nueva.
ok=""
if systemctl is-enabled --quiet "$SERVICIO" 2>/dev/null; then
  for _ in $(seq 1 60); do
    nueva="$(systemctl show "$SERVICIO" -p InvocationID --value)"
    if [ "$nueva" != "$INVOCACION" ] && [ "$(systemctl show "$SERVICIO" -p ActiveState --value)" = active ] \
      && curl -fsS --max-time 2 "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 1
  done
  if [ -z "$ok" ]; then
    echo "El backend no respondió con la versión $ID."
    if [ -n "$ANTERIOR" ]; then
      ln -sfn "$ANTERIOR" "$RAIZ/actual.nuevo" && mv -T "$RAIZ/actual.nuevo" "$RAIZ/actual"
      date -u +%FT%TZ > "$RAIZ/reiniciar"
      echo "Se volvió a $ANTERIOR."
    fi
    exit 1
  fi
  echo "Backend respondiendo en 127.0.0.1:$PUERTO"
else
  echo "El servicio todavía no está instalado (instalar-sistema.sh): queda lista para arrancar."
fi

# Limpieza: las últimas versiones (y siempre la activa).
ACTIVA="$(basename "$(readlink "$RAIZ/actual")")"
# Los ids empiezan con la fecha UTC del despliegue: orden por nombre.
mapfile -t VIEJAS < <(ls -1 "$RAIZ/versiones" | sort -r | grep -vx "$ACTIVA" | tail -n +"$VERSIONES_A_CONSERVAR")
for v in "${VIEJAS[@]}"; do
  [ -n "$v" ] && rm -rf "${RAIZ:?}/versiones/$v"
done
rm -f "$RAIZ"/subidas/*.tar.gz 2>/dev/null || true
"$UV" cache prune --quiet 2>/dev/null || true
