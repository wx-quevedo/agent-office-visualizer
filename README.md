# Oficina de agentes

Una oficina en vivo para ver qué hacen los agentes de Claude Code de Washington en todas sus máquinas: quién trabaja, quién espera un permiso o una respuesta, en qué tarea larga está cada uno, cuánto consume y dónde quedó cada proyecto. Se usa en https://agents.example.com, desde la PC y el celular.

El plan por etapas, las decisiones, el registro de cambios y los detalles de cada parte están en [PROJECT.md](PROJECT.md).

## Arquitectura

```
Claude Code (cada cuenta)                 Máquina (Windows)                         VPS (the VPS provider)
  hooks ─────────────────────────────▶  monitor  127.0.0.1:8765 ──https + token──▶  nginx  agents.example.com
  barra de estado (límites) ─────────▶   · cola SQLite sin conexión                  ├─ /      web estática (Next.js)
                                         · transcripciones y procesos                └─ /api   backend (FastAPI, systemd)
                                         · PROJECT.md de cada proyecto                         · motor de estados
                                                                                                · permisos, acceso, máquinas
navegador (PC, iPhone) ──https + sesión────────────────────────────────────────▶            · datos y respaldos diarios
```

- **Monitor** (`monitor/`): un proceso por máquina, sin ventana, que arranca solo al iniciar sesión. Recibe los hooks de Claude Code en 127.0.0.1 y guarda cada evento en una cola que sobrevive a cortes y reinicios. Lee las transcripciones, los procesos y el PROJECT.md de cada proyecto, toma los límites de 5 h y semanal de la barra de estado y lo envía todo al servidor. Es el único que conoce el token de la máquina. También resume cada aviso en una frase con un agente auxiliar aislado (`claude -p` con Haiku y la cuenta del agente; ver la etapa 2.4 en PROJECT.md).
- **Backend** (`backend/`): FastAPI en el VPS, detrás de nginx. Arma el estado de cada agente con su registro propio de eventos: esperas específicas, detector de atascos, historial por turno, tokens y tiempo. También atiende los permisos (aprobar o rechazar desde la oficina), el inicio de sesión y las máquinas.
- **Web** (`frontend/`): export estático de Next.js. Páginas: `/oficina/3d` (la oficina en 3D, también en la raíz), `/oficina` (vista de cajas), `/datos` (datos en bruto) y `/entrar`.
- **Hook** (`hooks/`): el paquete que Claude Code ejecuta en cada evento. Las máquinas con monitor lo llaman a través de él. Los comandos peligrosos (borrados recursivos, `git push --force`, `DROP TABLE`...) siempre piden aprobación, también en modo Auto.

## Desplegar al VPS

Desde `E:\visualizador-agentes`, en Git Bash, con el trabajo en un commit:

```bash
bash despliegue/desplegar.sh   # construye la web, sube el commit y reinicia el backend (sin sudo)
bash despliegue/estado.sh      # versión, servicio, respaldos, certificado y respuestas públicas
```

La instalación del sistema (una sola vez, con sudo), los respaldos y la restauración están en PROJECT.md, sección "VPS y despliegue".

## Instalar o actualizar el monitor

1. Crea el token de la máquina en el VPS (una vez por máquina):
   `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh token-crear --maquina <id>"`
2. Arma el instalador: `cd monitor; uv run python empaquetar.py` → `monitor/dist/instalar-visualizador-monitor.exe`.
3. Instalar: doble clic en ese archivo (pide la dirección del servidor y el token).
4. Actualizar sin pedir nada (conserva servidor, token y configuración): `& "E:\visualizador-agentes\monitor\dist\instalar-visualizador-monitor.exe" --actualizar`.
5. Desinstalar y dejar todo como estaba: el mismo archivo con `--desinstalar`.

## Desarrollo

```bash
make dev-local      # backend :8100 y web :3100 (sin tocar el uso diario)
cd backend && uv run pytest -q --timeout=300
cd hooks && uv run pytest -q
cd monitor && uv run pytest -q
cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run
```

## Origen

Empezó como una copia de Claude Office Visualizer (Paul Robello, licencia MIT, ver `LICENSE` y `THIRD_PARTY_NOTICES.md`). De aquel proyecto quedan el hook base y partes del backend; la web original se quitó en la etapa 1.4.
