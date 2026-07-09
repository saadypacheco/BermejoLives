-- ============================================================
-- Roles que Supabase Cloud crea automáticamente y que PostgREST
-- necesita para funcionar igual en self-host.
--
-- Este archivo corre UNA sola vez: docker-entrypoint-initdb.d solo se
-- ejecuta la primera vez que Postgres arranca con el volumen vacío. Por
-- eso no hace falta "if not exists" en los CREATE ROLE.
--
-- authenticator: rol de LOGIN que usa PostgREST para conectarse. Por cada
--   request, PostgREST hace SET LOCAL ROLE al rol indicado en el claim
--   "role" del JWT (anon / service_role) — por eso authenticator necesita
--   permiso para "convertirse" en esos roles (GRANT ... TO authenticator).
-- anon: rol sin login, usado por requests públicos (SELECT del catálogo).
-- authenticated: sin uso hoy (no hay login de comprador vía JWT de Postgres),
--   se crea solo porque las migraciones existentes lo referencian en GRANTs.
-- service_role: usado por los dos backends (FastAPI). Bypassa RLS entero,
--   igual que en Supabase Cloud.
-- ============================================================
\set authenticator_password `printf '%s' "$AUTHENTICATOR_PASSWORD"`

create role anon nologin noinherit;
create role authenticated nologin noinherit;
create role service_role nologin noinherit bypassrls;
create role authenticator login noinherit password :'authenticator_password';

grant anon to authenticator;
grant authenticated to authenticator;
grant service_role to authenticator;

-- Postgres 15+ ya no da USAGE en `public` a PUBLIC por defecto — explícito
-- acá para no depender de la versión.
grant usage on schema public to service_role;

-- pgcrypto: gen_random_uuid() (ya lo pide 0001_init.sql, pero no hace daño
-- dejarlo acá también para que el bootstrap sea autocontenido)
create extension if not exists "pgcrypto";
