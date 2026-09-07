#!/bin/bash
# Renueva el certificado real de Tailscale para el nombre .ts.net que sirve
# frontend/nginx.conf (ver el bloque `server_name debian.tailfc167d.ts.net`
# ahí), y reinicia el frontend solo si el certificado de verdad cambió.
#
# Pensado para correr por cron EN ESTE SERVIDOR, no en una máquina de
# desarrollo -la llave la emite `tailscale cert` para este nodo puntual de
# Tailscale, y copiada a otro lado no serviría de nada.
#
# `tailscale cert` es idempotente: si el certificado ya vigente todavía
# alcanza --min-validity, lo devuelve tal cual en vez de reemitir uno nuevo
# (probado a mano: dos corridas seguidas dan el mismo archivo, byte a byte).
# Por eso correr esto seguido -por ejemplo, una vez al día- no reinicia el
# frontend casi nunca: solo lo hace la vez que el certificado de verdad
# cambia, cerca de su vencimiento real (~90 días, es Let's Encrypt).
#
# Uso: ./certs/renovar_tailscale.sh
# Cron (instalado aparte, no por este script): ver docs o el mensaje de
# `deploy` que lo agregó.

set -euo pipefail

DOMINIO="debian.tailfc167d.ts.net"
DESTINO="/opt/gastronomo/certs"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

tailscale cert \
  --min-validity=720h \
  --cert-file="$TMP/fullchain.pem" \
  --key-file="$TMP/privkey.pem" \
  "$DOMINIO"

if cmp -s "$TMP/fullchain.pem" "$DESTINO/tailscale-fullchain.pem" 2>/dev/null; then
  echo "$(date -Is) certificado de $DOMINIO seguía vigente, nada que hacer"
  exit 0
fi

cp "$TMP/fullchain.pem" "$DESTINO/tailscale-fullchain.pem"
cp "$TMP/privkey.pem" "$DESTINO/tailscale-privkey.pem"
echo "$(date -Is) certificado de $DOMINIO renovado, reiniciando el frontend"

cd /opt/gastronomo && docker compose restart frontend
