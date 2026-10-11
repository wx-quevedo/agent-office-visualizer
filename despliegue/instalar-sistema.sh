#!/usr/bin/env bash
# Parte del despliegue que necesita sudo (una sola vez; se puede repetir sin daño).
# La ejecuta Washington:
#
#   ssh -t <VPS_USER>@<VPS_IP> "sudo bash ~/visualizador-agentes-instalacion/despliegue/instalar-sistema.sh"
#
# 1. Usuario del servicio "visualizador" (sin inicio de sesión ni privilegios).
# 2. Carpetas: código /var/www/visualizador-agentes (de <VPS_USER>, para desplegar sin
#    sudo), datos y respaldos /var/lib/visualizador-agentes (700, solo del servicio).
# 3. /etc/visualizador-agentes/backend.env con un secreto y una clave aleatorios
#    generados aquí (nunca se muestran ni salen del servidor).
# 4. systemd: backend (127.0.0.1:8320, se reinicia si se cae), reinicio al
#    desplegar y respaldo diario.
# 5. nginx: sitio agents.example.com (nginx -t antes de recargar; si falla,
#    se quita el sitio y no se recarga).
# 6. https con certbot (Let's Encrypt) y redirección de http a https; la
#    renovación automática es el certbot.timer que ya existe en el VPS.
# No toca ufw ni los demás sitios.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecutar con sudo."; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"
DUENO="${SUDO_USER:-<VPS_USER>}"

paso() { printf '\n== %s\n' "$*"; }

paso "0. Requisitos"
if ! python3 -c "import ensurepip, venv" 2>/dev/null; then
  apt-get install -y python3-venv
fi
echo "python3-venv disponible"

paso "1. Usuario del servicio"
if ! id "$USUARIO_SERVICIO" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATOS_RAIZ" --no-create-home --shell /usr/sbin/nologin "$USUARIO_SERVICIO"
  echo "Creado $USUARIO_SERVICIO"
else
  echo "Ya existe $USUARIO_SERVICIO"
fi

paso "2. Carpetas"
install -d -o "$USUARIO_SERVICIO" -g "$USUARIO_SERVICIO" -m 755 "$DATOS_RAIZ"
install -d -o "$USUARIO_SERVICIO" -g "$USUARIO_SERVICIO" -m 700 "$DATOS" "$RESPALDOS" "$DATOS_RAIZ/respaldos-backend"
install -d -o "$DUENO" -g "$DUENO" -m 755 "$RAIZ" "$RAIZ/versiones" "$RAIZ/subidas"
[ -e "$RAIZ/reiniciar" ] || install -o "$DUENO" -g "$DUENO" -m 644 /dev/null "$RAIZ/reiniciar"
ls -ld "$RAIZ" "$DATOS_RAIZ" "$DATOS" "$RESPALDOS"

paso "3. Configuración del backend"
install -d -o root -g "$USUARIO_SERVICIO" -m 750 "$CONFIG_DIR"
ENV="$CONFIG_DIR/backend.env"
if [ ! -f "$ENV" ]; then
  (
  umask 027
  SECRETO="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  CLAVE="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "$ENV" <<EOF
# Backend de la oficina de agentes en el VPS. Generado por instalar-sistema.sh.
# Contiene secretos: no copiar fuera del servidor.
VISUALIZADOR_AUTH=activado
VISUALIZADOR_SECRETO=$SECRETO
CLAUDE_OFFICE_API_KEY=$CLAVE
LECTURA_LOCAL=false
CONFIAR_PROXY=true
COOKIE_SEGURA=si
BACKEND_CORS_ORIGINS='["https://$DOMINIO"]'
STATE_EVENT_LOG_PATH=$DATOS/agent_events.db
DATABASE_URL=sqlite+aiosqlite:///$DATOS/visualizer.db
ACCESO_DB_PATH=$DATOS/acceso.db
RESPALDOS_PATH=$DATOS_RAIZ/respaldos-backend
MAQUINA_LOCAL_ID=alienware
MAQUINA_LOCAL_NOMBRE=Alienware
MAQUINA_LOCAL_SISTEMA=windows
LOG_RICH_TRACEBACKS=false
EOF
  )
  echo "Creado $ENV (secreto y clave generados aquí; no se muestran)"
else
  echo "Ya existe $ENV (se conserva: cambiar el secreto cerraría todas las sesiones)"
fi
chown root:"$USUARIO_SERVICIO" "$ENV"
chmod 640 "$ENV"

paso "4. systemd"
for u in visualizador-agentes.service visualizador-agentes-reinicio.path visualizador-agentes-reinicio.service \
         visualizador-agentes-respaldo.service visualizador-agentes-respaldo.timer; do
  install -o root -g root -m 644 "$DIR/systemd/$u" "/etc/systemd/system/$u"
done
systemctl daemon-reload
systemctl enable --now visualizador-agentes-reinicio.path visualizador-agentes-respaldo.timer
systemctl enable "$SERVICIO"
if [ -x "$RAIZ/actual/backend/.venv/bin/uvicorn" ]; then
  systemctl restart "$SERVICIO"
  echo "Backend arrancado"
else
  echo "Backend habilitado; arranca con el primer despliegue (desplegar.sh desde la PC)"
fi

paso "5. nginx"
install -o root -g root -m 644 "$DIR/nginx/seguridad.conf" /etc/nginx/snippets/visualizador-agentes-seguridad.conf
SITIO="/etc/nginx/sites-available/$DOMINIO"
if [ -f "$SITIO" ] && grep -q "managed by Certbot" "$SITIO"; then
  echo "El sitio ya tiene https de certbot: se conserva $SITIO"
else
  install -o root -g root -m 644 "$DIR/nginx/$DOMINIO" "$SITIO"
fi
ln -sfn "$SITIO" "/etc/nginx/sites-enabled/$DOMINIO"
if ! nginx -t; then
  rm -f "/etc/nginx/sites-enabled/$DOMINIO"
  echo "nginx -t falló: se quitó el sitio nuevo y no se recargó nginx."
  exit 1
fi
systemctl reload nginx
echo "nginx recargado"

paso "6. https"
IP_VPS="<VPS_IP>"
if ! getent ahostsv4 "$DOMINIO" | awk '{print $1}' | grep -qx "$IP_VPS"; then
  echo "$DOMINIO todavía no resuelve a $IP_VPS: no se pide el certificado. Repetir más tarde."
  exit 1
fi
certbot --nginx -d "$DOMINIO" --non-interactive --keep-until-expiring --redirect
nginx -t
systemctl reload nginx
systemctl is-enabled certbot.timer >/dev/null && echo "Renovación automática: certbot.timer activo"

paso "Listo"
echo "Siguiente: desde la PC, bash despliegue/desplegar.sh (si todavía no se desplegó)."
