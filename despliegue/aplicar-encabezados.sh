#!/usr/bin/env bash
# Instala los encabezados de seguridad de la oficina (CSP incluida) en nginx, sin
# tocar nada más. Lo ejecuta Washington después de un cambio en nginx/seguridad.conf:
#
#   ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/aplicar-encabezados.sh"
#
# Valida con nginx -t antes de recargar; si falla, deja el archivo anterior.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecutar con sudo."; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
cd /
DESTINO=/etc/nginx/snippets/visualizador-agentes-seguridad.conf
ANTERIOR="$(mktemp)"
trap 'rm -f "$ANTERIOR"' EXIT
cp -p "$DESTINO" "$ANTERIOR"
install -o root -g root -m 644 "$DIR/nginx/seguridad.conf" "$DESTINO"
if ! nginx -t; then
  cp -p "$ANTERIOR" "$DESTINO"
  echo "nginx -t falló: se dejó el archivo anterior y no se recargó nginx."
  exit 1
fi
systemctl reload nginx
echo "Encabezados aplicados y nginx recargado."
grep -o 'Content-Security-Policy "[^"]*"' "$DESTINO"
