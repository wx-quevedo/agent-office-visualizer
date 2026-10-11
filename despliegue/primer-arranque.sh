#!/usr/bin/env bash
# Segundo paso con sudo, después del primer despliegue. Lo ejecuta Washington:
#
#   ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/primer-arranque.sh"
#
# 1. Pide la contraseña de la oficina (dos veces, sin eco; solo se guarda su hash
#    argon2), salvo que ya exista o se pase --sin-contrasena.
# 2. Hace un respaldo ahora y lo prueba restaurándolo en una copia.
# 3. Prueba que el backend vuelve solo si se cae (kill -9).
# 4. Muestra el estado del servicio, del respaldo diario y del certificado.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecutar con sudo."; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
# El usuario del servicio no puede entrar al directorio de quien lo llama
# (por ejemplo /home/<VPS_USER>): todo corre desde la raíz.
cd /

SIN_CONTRASENA=""
[ "${1:-}" = "--sin-contrasena" ] && SIN_CONTRASENA=1

hay_contrasena() {
  [ -f "$DATOS/acceso.db" ] || return 1
  sudo -u "$USUARIO_SERVICIO" python3 -I -c '
import sqlite3, sys
db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    sys.exit(0 if db.execute("SELECT 1 FROM usuario WHERE id = 1").fetchone() else 1)
finally:
    db.close()
' "$DATOS/acceso.db"
}

echo "== 1. Contraseña de la oficina"
if [ -n "$SIN_CONTRASENA" ]; then
  echo "Se omite (--sin-contrasena)."
elif hay_contrasena; then
  echo "Ya hay una contraseña: se omite (para cambiarla: acceso.sh contrasena)."
else
  bash "$DIR/acceso.sh" contrasena
fi

echo
echo "== 2. Respaldo ahora y prueba de restauración en una copia"
salida="$(sudo -u "$USUARIO_SERVICIO" bash "$DIR/respaldar.sh")"
echo "$salida"
ultimo="$(printf '%s\n' "$salida" | sed -n 's/^Respaldo: //p')"
sudo -u "$USUARIO_SERVICIO" bash "$DIR/restaurar.sh" --copia "$ultimo"

echo
echo "== 3. Caída del backend (kill -9): debe volver solo"
antes="$(systemctl show "$SERVICIO" -p MainPID --value)"
reinicios="$(systemctl show "$SERVICIO" -p NRestarts --value)"
systemctl kill -s KILL "$SERVICIO"
volvio=""
for _ in $(seq 1 30); do
  sleep 1
  ahora="$(systemctl show "$SERVICIO" -p MainPID --value)"
  if [ "$ahora" != "0" ] && [ "$ahora" != "$antes" ]     && curl -fsS --max-time 2 "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1; then
    volvio=1
    break
  fi
done
if [ -n "$volvio" ]; then
  echo "Volvió solo: PID $antes -> $ahora; reinicios $reinicios -> $(systemctl show "$SERVICIO" -p NRestarts --value)"
else
  echo "NO volvió en 30 s: revisar journalctl -u $SERVICIO"
fi

echo
echo "== 4. Estado"
systemctl is-active "$SERVICIO" visualizador-agentes-reinicio.path visualizador-agentes-respaldo.timer || true
systemctl list-timers visualizador-agentes-respaldo.timer --no-pager | head -3
certbot certificates --cert-name "$DOMINIO" 2>/dev/null | grep -E "Expiry|Domains" || true
