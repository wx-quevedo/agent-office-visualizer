#!/usr/bin/env bash
# Actualiza el VPS con el commit actual, desde la PC (Git Bash), sin sudo y sin
# credenciales de GitHub en el servidor:
#
#   bash despliegue/desplegar.sh            # el commit actual (HEAD)
#   bash despliegue/desplegar.sh --sin-front   # reutiliza frontend/out ya construido
#   bash despliegue/desplegar.sh --arbol       # el árbol de trabajo con sus cambios
#                                              # (pruebas; la versión dice "+cambios")
#
# 1. Construye el export estático del frontend con la API en el mismo dominio.
# 2. Arma un tar con "git archive" del commit (backend, despliegue, frontend/public)
#    y el export estático, y lo sube por ssh.
# 3. En el VPS: activar-version.sh (entorno, enlace atómico, reinicio, /health,
#    vuelta atrás si falla).
# Exige el árbol de trabajo limpio: lo que se despliega es exactamente un commit.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
RAIZ_REPO="$(cd "$DIR/.." && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
cd "$RAIZ_REPO"

SIN_FRONT=""
ARBOL=""
for a in "$@"; do
  case "$a" in
    --sin-front) SIN_FRONT=1 ;;
    --arbol) ARBOL=1 ;;
    *) echo "Opción desconocida: $a"; exit 1 ;;
  esac
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
COMMIT="$(git rev-parse --short HEAD)"
if [ -n "$ARBOL" ]; then
  # Una foto del árbol de trabajo (también los archivos nuevos no ignorados) con
  # un índice temporal: no cambia el índice ni los commits del repositorio.
  cp "$(git rev-parse --git-dir)/index" "$TMP/indice"
  GIT_INDEX_FILE="$TMP/indice" git add -A
  ORIGEN="$(GIT_INDEX_FILE="$TMP/indice" git write-tree)"
  COMMIT="$COMMIT+cambios"
else
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Hay cambios sin commit: se despliega solo un commit (o usa --arbol para pruebas)."
    exit 1
  fi
  ORIGEN="HEAD"
fi
ID="$(date -u +%Y%m%d-%H%M%S)-${COMMIT/+cambios/-cambios}"

if [ -z "$SIN_FRONT" ]; then
  echo "== Frontend (export estático para https://$DOMINIO)"
  (
    cd frontend
    NEXT_PUBLIC_API_URL="https://$DOMINIO" npm run build
  )
fi
[ -f frontend/out/index.html ] || { echo "Falta frontend/out (construir el frontend)."; exit 1; }

echo "== Paquete $ID"
git archive --format=tar --prefix="$ID/" "$ORIGEN" backend despliegue frontend/public > "$TMP/paquete.tar"
mkdir -p "$TMP/$ID"
cp -r frontend/out "$TMP/$ID/frontend-out"
echo "$COMMIT" > "$TMP/$ID/VERSION"
tar -rf "$TMP/paquete.tar" -C "$TMP" "$ID/frontend-out" "$ID/VERSION"
gzip -9 "$TMP/paquete.tar"
du -h "$TMP/paquete.tar.gz" | cut -f1

echo "== Subida y activación"
ssh -o BatchMode=yes "$VPS" "mkdir -p $RAIZ/subidas && cat > $RAIZ/subidas/$ID.tar.gz" < "$TMP/paquete.tar.gz"
ssh -o BatchMode=yes "$VPS" "set -e; tar -xzf $RAIZ/subidas/$ID.tar.gz -C $RAIZ/versiones && bash $RAIZ/versiones/$ID/despliegue/activar-version.sh $ID"
echo "Desplegado $COMMIT en https://$DOMINIO"
