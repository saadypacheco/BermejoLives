# ---- build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# NEXT_PUBLIC_* se hornean en el bundle del navegador (apuntan a localhost del host)
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL
# El mapa base. Si no viene, mapa-tiles.ts cae a OpenStreetMap directo.
ARG NEXT_PUBLIC_TILES_URL
ENV NEXT_PUBLIC_TILES_URL=$NEXT_PUBLIC_TILES_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# Versión: commit y ambiente con los que se buildeó (se hornean en el bundle)
ARG GIT_SHA
ARG APP_ENV
ENV GIT_SHA=$GIT_SHA
ENV APP_ENV=$APP_ENV
RUN npm run build

# ---- run ----
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm install --omit=dev
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./
EXPOSE 3003
# next start respeta el -p del script dev? No: usamos start con -p 3003 y -H 0.0.0.0
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3003"]
