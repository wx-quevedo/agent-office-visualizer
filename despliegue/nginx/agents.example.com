# Sitio de nginx de la oficina de agentes. Lo instala despliegue/instalar-sistema.sh
# en /etc/nginx/sites-available/agents.example.com. Como los demás sitios del VPS,
# solo escucha en el 80: certbot --nginx agrega el bloque 443 con el certificado y
# la redirección de HTTP a HTTPS.
#
# - Frontend: export estático de Next.js (construido en la PC), servido por nginx.
# - /api: al backend en 127.0.0.1:8320 (systemd visualizador-agentes).

# Nombre propio para no chocar con los upstream de otros sitios.
upstream visualizador_backend {
    server 127.0.0.1:8320;
    keepalive 16;
}

server {
    listen 80;
    listen [::]:80;
    server_name agents.example.com;

    root /var/www/visualizador-agentes/actual/frontend-out;
    index index.html;
    autoindex off;
    server_tokens off;
    charset utf-8;

    # Eventos y observaciones de los monitores (lotes de hasta 200 sesiones).
    client_max_body_size 4m;
    client_body_timeout 30s;

    access_log /var/log/nginx/visualizador-agentes.access.log;
    error_log /var/log/nginx/visualizador-agentes.error.log;

    include /etc/nginx/snippets/visualizador-agentes-seguridad.conf;

    # gzip solo en este sitio (el nginx.conf del VPS comprime solo HTML).
    gzip_types text/css application/javascript application/json image/svg+xml text/plain;
    gzip_min_length 1024;

    # API. La espera de un permiso es una consulta larga de hasta 25 s y el hook
    # espera hasta 600 s en total: tiempos holgados (660 s).
    location /api/ {
        proxy_pass http://visualizador_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 660s;
        proxy_send_timeout 660s;
        proxy_buffering off;
        proxy_redirect off;
    }

    # Documentación de la API: no se publica.
    location ~ ^/(docs|redoc|openapi\.json)(/|$) {
        return 404;
    }

    # Archivos con huella de Next.js: caché larga.
    location /_next/static/ {
        include /etc/nginx/snippets/visualizador-agentes-seguridad.conf;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        try_files $uri =404;
    }

    # Páginas: /entrar -> entrar.html; sin caché (cambian con cada versión).
    location / {
        include /etc/nginx/snippets/visualizador-agentes-seguridad.conf;
        add_header Cache-Control "no-cache" always;
        try_files $uri $uri.html $uri/index.html =404;
    }

    # Ningún archivo oculto (.git, .env...).
    location ~ /\. {
        return 404;
    }

    error_page 404 /404.html;
}
