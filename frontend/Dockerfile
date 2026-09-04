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
# final. Tiene que ser la URL que el NAVEGADOR pueda alcanzar (la IP/dominio
# real del servidor), nunca un nombre de servicio de docker compose como
# "backend": el navegador de quien usa la app no vive dentro de esa red.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=10s \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
