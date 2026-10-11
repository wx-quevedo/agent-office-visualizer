#!/usr/bin/env bash
# Comandos de acceso del backend en el VPS (contraseña, máquinas, tokens, sesiones),
# con la configuración del servicio y como su usuario. Los ejecuta Washington:
#
#   ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh contrasena"
#   ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh maquinas"
#
# (los mismos subcomandos que app.acceso_cli: contrasena, maquinas, maquina-crear,
# token-crear, tokens, token-revocar, sesiones, sesion-revocar).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecutar con sudo."; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
[ $# -ge 1 ] || { echo "Uso: acceso.sh <subcomando> [opciones]"; exit 1; }
cd "$RAIZ/actual/backend"
# El secreto se lee dentro del proceso del servicio (nunca en la línea de comandos).
exec sudo -u "$USUARIO_SERVICIO" -- bash -c   'set -a; source "$0"; set +a; export HOME="$1"; shift; exec .venv/bin/python -m app.acceso_cli "$@"'   "$CONFIG_DIR/backend.env" "$DATOS_RAIZ" "$@"
