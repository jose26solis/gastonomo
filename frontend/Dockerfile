# Build de dos etapas: Node solo hace falta para compilar -el contenedor
# final es nginx sirviendo archivos estáticos, mucho más liviano que dejar
# Node corriendo todo el tiempo para esto (que es lo que hacía
# 'vite preview', la alternativa más simple pero más pesada en RAM).

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Vite hornea VITE_API_URL en el bundle en tiempo de build, no de arranque
# -por eso es un ARG del build y no una variable de entorno del contenedor
# final. Por defecto queda vacío a propósito: nginx.conf hace de proxy del
# backend bajo el mismo origen HTTPS (ver la nota ahí), así que "" produce
# rutas relativas ("/api/..."), no una URL absoluta a otro origen -eso es
# lo que evita que el navegador bloquee las llamadas como contenido mixto.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
# 127.0.0.1 explícito, no "localhost": nginx.conf no es byte-idéntico al
# default.conf de la imagen, así que el entrypoint no le agrega el listen
# en IPv6 que sí le pondría al de fábrica -"localhost" adentro del
# contenedor resuelve primero a ::1 y el healthcheck fallaba con
# "Connection refused" aunque el sitio respondiera bien por IPv4 (que es
# como llega cualquier tráfico real, LAN o navegador). --no-check-certificate
# porque el certificado es autofirmado -ver la nota de arriba de todo en
# nginx.conf- así que wget lo rechazaría por no confiable si no se lo decimos.
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=10s \
    CMD wget --no-check-certificate -qO- https://127.0.0.1/ >/dev/null || exit 1
