#!/bin/bash
# Genera un certificado autofirmado para que nginx (frontend) sirva HTTPS.
#
# Por qué hace falta: Azure y Google Cloud no dejan registrar un redirect
# URI de OAuth en HTTP plano salvo que sea literalmente "http://localhost"
# -una IP de LAN por HTTP queda rechazada con "Must start with HTTPS or
# http://localhost". Un certificado autofirmado no lo emite una autoridad
# de confianza (el navegador va a avisar "conexión no segura" la primera
# vez, hay que aceptar el riesgo para seguir), pero para el intercambio de
# OAuth en sí no importa: Microsoft/Google nunca abren esa URL del lado del
# servidor, es el navegador del titular el que navega ahí directo, así que
# la cadena de confianza del certificado no entra en el chequeo de ellos
# -solo exigen que el esquema sea "https".
#
# Uso:
#   ./certs/generar.sh 192.168.100.89
#   ./certs/generar.sh mi-dominio.com
#
# Genera certs/fullchain.pem y certs/privkey.pem -docker-compose.yml ya los
# monta en el contenedor del frontend. Válido 825 días (el máximo que Apple
# todavía acepta sin quejarse en Safari/iOS); volvé a correr este script
# para renovarlo.

set -euo pipefail

HOST="${1:?Uso: ./certs/generar.sh <ip-o-dominio>}"
DIR="$(dirname "$0")"

# Si HOST es una IP (todo dígitos y puntos), el SAN tiene que declararla
# como IP:, no como DNS: -los navegadores actuales ignoran el CN y solo
# miran el Subject Alternative Name, y del tipo que corresponda.
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="IP:${HOST}"
else
  SAN="DNS:${HOST}"
fi

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "${DIR}/privkey.pem" \
  -out "${DIR}/fullchain.pem" \
  -subj "/CN=${HOST}" \
  -addext "subjectAltName=${SAN}"

echo "Listo: ${DIR}/fullchain.pem y ${DIR}/privkey.pem para ${HOST}."
echo "Reconstruí/reiniciá el contenedor del frontend para que los tome:"
echo "  docker compose up -d --force-recreate frontend"
