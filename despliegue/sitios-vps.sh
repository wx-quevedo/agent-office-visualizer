#!/usr/bin/env bash
# Huella de los demás sitios del VPS (desde la PC): estado HTTP, redirección y
# tamaño de la portada por https y http. Sirve para comparar antes y después de
# tocar nginx: la salida debe ser igual.
#
#   bash despliegue/sitios-vps.sh > antes.txt
#   ... cambios ...
#   bash despliegue/sitios-vps.sh > despues.txt && diff antes.txt despues.txt
set -u
SITIOS=(
  admin.vivedemo.example.com api.vivedemo.example.com brainstorming.example.net
  buscapez.com www.buscapez.com design.buscapez.com localia.cc www.localia.cc
  productividad.example.com projection.example.com skynest.example.com
  vivedemo.example.com
)
# En Windows (Git Bash) el curl de Git falla con https (Schannel): se usa el de Windows.
CURL=curl
NULO=/dev/null
if [ -x /c/Windows/System32/curl.exe ]; then CURL=/c/Windows/System32/curl.exe; NULO=NUL; fi
for s in "${SITIOS[@]}"; do
  for esquema in https http; do
    r=$("$CURL" -s -o "$NULO" --max-time 20 -w '%{http_code} %{redirect_url} %{size_download} %{ssl_verify_result}' "$esquema://$s/")
    echo "$esquema://$s/ $r"
  done
done
