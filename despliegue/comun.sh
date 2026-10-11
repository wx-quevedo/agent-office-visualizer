# Valores compartidos por los scripts de despliegue (se cargan con "source").
# shellcheck shell=bash

VPS="${VPS:-<VPS_USER>@<VPS_IP>}"
DOMINIO="agents.example.com"
# Código (una carpeta por versión, "actual" apunta a la activa); de <VPS_USER>.
RAIZ="/var/www/visualizador-agentes"
# Datos y respaldos: solo del usuario del servicio (700).
# (VISUALIZADOR_DATOS_RAIZ solo para probar los scripts en otra carpeta.)
DATOS_RAIZ="${VISUALIZADOR_DATOS_RAIZ:-/var/lib/visualizador-agentes}"
DATOS="$DATOS_RAIZ/datos"
RESPALDOS="$DATOS_RAIZ/respaldos"
# Configuración con el secreto (640 root:visualizador).
CONFIG_DIR="/etc/visualizador-agentes"
USUARIO_SERVICIO="visualizador"
SERVICIO="visualizador-agentes"
PUERTO="8320"
# Versiones que se conservan para volver atrás.
VERSIONES_A_CONSERVAR=3
