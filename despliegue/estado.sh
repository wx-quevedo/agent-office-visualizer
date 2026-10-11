#!/usr/bin/env bash
# Estado de la oficina en el VPS, desde la PC (sin sudo):
#
#   bash despliegue/estado.sh
#
# Versión activa, servicio, /health, último respaldo, certificado, disco, y las
# respuestas públicas (página /entrar, API sin sesión = 401).
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=comun.sh
source "$DIR/comun.sh"

ssh -o BatchMode=yes "$VPS" "bash -s" <<EOF
echo "== Versión activa: \$(cat $RAIZ/actual/VERSION 2>/dev/null) (\$(basename \$(readlink $RAIZ/actual) 2>/dev/null))"
echo "== Servicio: \$(systemctl is-active $SERVICIO) (desde \$(systemctl show $SERVICIO -p ActiveEnterTimestamp --value)); reinicios: \$(systemctl show $SERVICIO -p NRestarts --value)"
echo "== Reinicio al desplegar: \$(systemctl is-active visualizador-agentes-reinicio.path); respaldo diario: \$(systemctl is-active visualizador-agentes-respaldo.timer)"
echo "== /health: \$(curl -s --max-time 3 http://127.0.0.1:$PUERTO/health)"
echo "== Respaldo:"; sed 's/^/   /' $DATOS_RAIZ/estado-respaldo.txt 2>/dev/null || echo "   (todavía ninguno)"
echo "== Próximo respaldo: \$(systemctl show visualizador-agentes-respaldo.timer -p NextElapseUSecRealtime --value)"
echo "== Disco: \$(df -h / | awk 'NR==2{print \$4" libres de "\$2" ("\$5" usado)"}')"
echo "== Versiones guardadas: \$(ls -1 $RAIZ/versiones | tr '\n' ' ')"
EOF

CURL=curl; NULO=/dev/null
if [ -x /c/Windows/System32/curl.exe ]; then CURL=/c/Windows/System32/curl.exe; NULO=NUL; fi
echo "== Público"
echo "   /entrar: $("$CURL" -s -o "$NULO" --max-time 15 -w '%{http_code} (certificado %{ssl_verify_result})' "https://$DOMINIO/entrar")"
echo "   /api sin sesión: $("$CURL" -s -o "$NULO" --max-time 15 -w '%{http_code}' "https://$DOMINIO/api/v1/agents/state")"
echo "   http -> https: $("$CURL" -s -o "$NULO" --max-time 15 -w '%{http_code} %{redirect_url}' "http://$DOMINIO/")"
FIN="$(echo | openssl s_client -servername "$DOMINIO" -connect "$DOMINIO:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
echo "   certificado vence: ${FIN:-(no se pudo leer)}"
