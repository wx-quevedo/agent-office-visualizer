"""Enmascarado de secretos en textos de avisos (etapa 2.4).

El mismo archivo vive en el monitor (``visualizador_monitor/secretos.py``) y en el
backend (``app/core/secretos.py``): los dos lados aplican la misma regla. Si se
cambia uno, se copia al otro (las pruebas de ambos usan los mismos casos).

Tapa tokens con prefijos conocidos, JWT, encabezados de autorización, cookies,
credenciales en URL y en opciones de comandos (mysql -p, sqlcmd -P, sshpass -p,
curl -u, net user...), nombre=valor cuando el nombre habla de claves, claves
privadas y cadenas largas al azar. No toca rutas, SHA de git ni UUID.
"""

from __future__ import annotations

import re

SECRETO = "[secreto]"

# Nombres de variables u opciones que guardan secretos ("auth" sí, "author" no).
_NOMBRES = (
    r"(?:pass(?:word|wd|phrase)?|pwd|secret|token|api[_-]?key|apikey|access[_-]?key"
    r"|account[_-]?key|private[_-]?key|client[_-]?secret|credentials?|auth(?!or|entication)"
    r"|(?<![a-z])pat(?![a-z])|sig(?:nature)?)"
)
# Valores que no son secretos: marcadores, booleanos y variables.
_NO_SECRETO = r"(?!(?:\?|true|false|null|none|%s|\$\w+|\{\w+\})(?:[\s;&|,}'\"]|$))"
_VALOR = r"(?:\"[^\"]*\"|'[^']*'|[^\s;&|,}]+)"

_PATRONES: list[tuple[re.Pattern[str], str]] = [
    # Bloques de claves privadas.
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", re.S
        ),
        SECRETO,
    ),
    # Credenciales en una URL: esquema://usuario:clave@host
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.I), r"\1" + SECRETO + "@"),
    # Webhooks de Slack y Discord (la URL entera es la credencial).
    (
        re.compile(
            r"https?://(?:hooks\.slack\.com/services|discord(?:app)?\.com/api/webhooks)/\S+"
        ),
        SECRETO,
    ),
    # Parámetros de URL con firmas o tokens (SAS de Azure, OAuth).
    (
        re.compile(r"([?&](?:sig|signature|access_token|code|token|key)=)[^&\s'\"]+", re.I),
        r"\1" + SECRETO,
    ),
    # Encabezados: Authorization: Bearer x, Cookie: x.
    (
        re.compile(r"\b(authorization\s*:\s*(?:bearer|basic|token)?\s*)[^\s'\"]+", re.I),
        r"\1" + SECRETO,
    ),
    (re.compile(r"\b(bearer\s+)[\w\-.~+/=]{8,}", re.I), r"\1" + SECRETO),
    (re.compile(r"\b((?:set-)?cookie\s*:\s*)[^'\"\n]+", re.I), r"\1" + SECRETO),
    # JWT.
    (re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"), SECRETO),
    # Prefijos conocidos (Anthropic, OpenAI, GitHub, GitLab, Slack, AWS, Google,
    # npm, Hugging Face, Stripe y los tokens del visualizador).
    (
        re.compile(
            r"\b(?:sk-ant-[\w-]{8,}|sk-[\w-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|github_pat_\w{16,}"
            r"|glpat-[\w-]{12,}|xox[abprs]-[\w-]{8,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,}"
            r"|npm_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|[rs]k_(?:live|test)_\w{10,}|va[msp]_[\w-]{8,})"
        ),
        SECRETO,
    ),
    # Contraseñas en opciones cortas de programas conocidos.
    (
        re.compile(r"(\b(?:mysql|mariadb|mysqldump)\b[^|;&\n]*?\s-p)(?!\s*-)\s*" + _VALOR, re.I),
        r"\1" + SECRETO,
    ),
    (re.compile(r"(\b(?:sqlcmd|bcp|zip)\b[^|;&\n]*?\s-P\s+)" + _VALOR), r"\1" + SECRETO),
    (
        re.compile(r"(\b(?:sshpass|docker|podman|helm|az)\b[^|;&\n]*?\s-p\s+)" + _VALOR, re.I),
        r"\1" + SECRETO,
    ),
    (re.compile(r"(\bredis-cli\b[^|;&\n]*?\s-a\s+)" + _VALOR, re.I), r"\1" + SECRETO),
    (re.compile(r"(\bopenssl\b[^|;&\n]*?\s-(?:k|pass)\s+)" + _VALOR, re.I), r"\1" + SECRETO),
    (re.compile(r"(\b7z\b[^|;&\n]*?\s-p)" + _VALOR), r"\1" + SECRETO),
    (re.compile(r"((?:\s-u|--user)\s+[^\s:'\"]+:)" + _VALOR, re.I), r"\1" + SECRETO),
    (re.compile(r"(\bnet\s+user\s+\S+\s+)(?!/)" + _VALOR, re.I), r"\1" + SECRETO),
    (re.compile(r"(/user:\S+\s+)(?!/)" + _VALOR, re.I), r"\1" + SECRETO),
    (
        re.compile(r"(ConvertTo-SecureString\s+(?:-String\s+)?)" + _VALOR, re.I),
        r"\1" + SECRETO,
    ),
    (re.compile(r"\becho\s+" + _VALOR + r"(\s*\|\s*sudo\s+-S)", re.I), "echo " + SECRETO + r"\1"),
    (
        re.compile(
            r"(SetEnvironmentVariable\(\s*['\"][^'\"]*"
            + _NOMBRES
            + r"[^'\"]*['\"]\s*,\s*)"
            + _VALOR,
            re.I,
        ),
        r"\1" + SECRETO,
    ),
    # Nombre=valor (variables, JSON, cadenas de conexión) cuando el nombre habla de claves.
    (
        re.compile(
            r"(?P<n>(?:\$env:|\$)?[\w.-]*"
            + _NOMBRES
            + r"[\w.-]*[\"']?)(?P<s>\s*[:=]\s*)"
            + _NO_SECRETO
            + r"(?P<v>"
            + _VALOR
            + r")",
            re.I,
        ),
        r"\g<n>\g<s>" + SECRETO,
    ),
    # Opciones de comandos: --password valor, -Token valor.
    (
        re.compile(
            r"(?P<n>(?<![\w-])--?[\w-]*"
            + _NOMBRES
            + r"[\w-]*)(?P<s>\s+)"
            + _NO_SECRETO
            + r"(?P<v>"
            + _VALOR
            + r")",
            re.I,
        ),
        r"\g<n>\g<s>" + SECRETO,
    ),
    # Cadenas largas al azar (letras y números, 32 o más), sin cruzar barras: no se
    # comen rutas. No tapa SHA de git (40 hex) ni UUID.
    (
        re.compile(
            r"(?<![\w.\-/\\])(?![0-9a-f]{40}(?![\w+=-]))"
            r"(?![0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![\w+=-]))"
            r"(?=[A-Za-z0-9+_=-]*\d)(?=[A-Za-z0-9+_=-]*[A-Za-z])[A-Za-z0-9+_=-]{32,}",
            re.I,
        ),
        SECRETO,
    ),
]


def enmascarar(texto: str) -> str:
    """El texto sin claves, tokens ni contraseñas reconocibles."""
    for patron, reemplazo in _PATRONES:
        texto = patron.sub(reemplazo, texto)
    return texto


def parece_dato(palabra: str) -> bool:
    """Una palabra con forma de clave o de identificador al azar: larga, con
    mayúsculas y minúsculas mezcladas o con letras y números juntos."""
    w = palabra.strip(".,;:!?¿¡()\"'")
    if len(w) < 10:
        return False
    mayus = sum(c.isupper() for c in w)
    minus = sum(c.islower() for c in w)
    digitos = sum(c.isdigit() for c in w)
    return (mayus >= 4 and minus >= 2) or (digitos >= 2 and mayus + minus >= 4)


def palabras_raras(texto: str) -> set[str]:
    """Tramos del texto que parecen datos (letras y números, o con símbolos): si la
    frase del auxiliar repite alguno, podría estar copiando un secreto."""
    salida: set[str] = set()
    for w in re.findall(r"[^\s'\"=:;,()]{6,}", texto):
        mezcla = re.search(r"\d", w) and re.search(r"[A-Za-z]", w)
        if mezcla or re.search(r"[^\w\s.\-/\\¿?¡!áéíóúñÁÉÍÓÚÑ]", w):
            salida.add(w.lower())
    return salida
