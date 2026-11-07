# ---- build ----
FROM node:22-alpine AS builder
WORKDIR /app
# `npm ci`: instala EXACTAMENTE lo del package-lock.json (y falla si no coincide
# con package.json). Con `npm install` un build podía traer versiones distintas.
COPY package*.json ./
RUN npm ci
COPY . .

# Sólo se hornean en el bundle del navegador las NEXT_PUBLIC_* que son públicas de
# verdad: la API y el mapa. La base (PostgREST) y su anon key NO van al bundle: el
# servidor de Next las lee por la red interna (lib/supabase.ts, `server-only`).
ARG NEXT_PUBLIC_API_URL
# El mapa base. Si no viene, mapa-tiles.ts cae a OpenStreetMap directo.
ARG NEXT_PUBLIC_TILES_URL
ENV NEXT_PUBLIC_TILES_URL=$NEXT_PUBLIC_TILES_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# EL BUILD NO LEE LA BASE (auditoría 5/11, A-02 paso 3): por eso ya no hay ARG de SUPABASE_*.
# `docker build` (BuildKit) no entra a las redes del compose y el router público `db.` está
# cerrado. Las páginas que dependen de datos (/que-es-uruku, /comprar-en-bermejo, fichas,
# ciudades, rubros) se arman en el primer pedido y se regeneran por ISR; el sitemap y llms.txt
# se arman al pedido. En runtime el contenedor recibe SUPABASE_INTERNAL_URL / SUPABASE_ANON_KEY
# como `environment` (docker-compose.prod.yml).
# Versión: commit y ambiente con los que se buildeó (se hornean en el bundle)
ARG GIT_SHA
ARG APP_ENV
ENV GIT_SHA=$GIT_SHA
ENV APP_ENV=$APP_ENV
RUN npm run build

# ---- run ----
FROM node:22-alpine
ENV NODE_ENV=production
# Usuario no root: `node` (uid 1000) ya viene en la imagen. /app es suyo para que
# Next pueda crear `.next/cache` si lo necesita; lo demás es sólo lectura de hecho.
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --chown=node:node --from=builder /app/.next ./.next
COPY --chown=node:node --from=builder /app/public ./public
# Los manuales en Markdown: /que-es-uruku se arma en el primer pedido (no en el build) y lee
# content/manuales/uruku.md en ese momento. Sólo lectura.
COPY --chown=node:node --from=builder /app/content ./content
COPY --chown=node:node --from=builder /app/next.config.mjs ./
EXPOSE 3003
# Directo al binario (sin `npx`, que podría intentar bajar nada de internet al arrancar).
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3003"]
