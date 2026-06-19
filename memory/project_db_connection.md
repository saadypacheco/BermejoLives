---
name: project-db-connection
description: URL de conexión directa a la base de datos de producción (Supabase Cloud)
metadata:
  type: project
---

Supabase Cloud session pooler URL (para migraciones vía psql/Docker):
`postgresql://postgres.lzknugpogpkcxjcpuqes:Sgenerico.1989@aws-1-us-west-2.pooler.supabase.com:5432/postgres`

Project ref: `lzknugpogpkcxjcpuqes`
Region: `aws-1-us-west-2`

**Why:** Se usa para correr migraciones en producción vía Docker cuando no hay psql ni npx en el VPS.
**How to apply:** Usar con `docker run --rm -v .../migrations:/migrations postgres:16 psql "URL" -f /migrations/XXXX.sql`

La DATABASE_URL debe estar en `/docker/buscadonde/.env` en el VPS.
