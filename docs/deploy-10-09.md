# Deploy del 10/9 — paso a paso

> 18 commits y 3 migraciones. Es el deploy más grande en un rato, así que va
> partido en pasos con una verificación en cada uno: si algo sale mal, se sabe
> **cuál** de los pasos falló y no hay que adivinar.
>
> Todo se corre en el VPS, dentro de `/docker/uruku`.

## Qué entra

| | |
|---|---|
| **Difusión a redes** | La oferta aprobada sale sola al canal, Facebook e Instagram. Nueva pestaña Admin › Difusión. |
| **Planes en la base** | Precios, cuotas y el costo de la publicación extra, editables desde el panel. |
| **Cuotas de publicación** | Se cuentan de verdad, y al llegar al tope se avisa por WhatsApp. |
| **Informe de demanda** | Nueva pestaña Admin › Demanda. |
| **Tope del canal** | 4 publicaciones por día; lo que no entra espera. |
| **Capa de Meta** | El webhook acepta la API oficial, sin migrar nada todavía. |
| **Agregar respaldos a los grupos** | Botón en Admin › WhatsApp. |

---

## Paso 0 — De dónde venimos

```bash
curl -s https://uruku.bo/version
```

**Anotá el `sha` que devuelve.** Es a lo que hay que volver si algo sale mal, y
en dos horas ya no te vas a acordar.

---

## Paso 1 — Traer el código

```bash
cd /docker/uruku
git pull
git log --oneline -1
```

---

## Paso 2 — Las migraciones, una por una

**No las corras juntas.** Si falla la segunda, querés saber que la primera
entró.

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -f - < selfhost/postgres-init/0100_cola_de_difusion.sql
```

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -f - < selfhost/postgres-init/0101_planes_en_la_base.sql
```

La 0101 es la única que toca una tabla existente (`comercios`). Va a imprimir
`NOTICE: quitando el CHECK … de comercios.plan` — eso es lo esperado. Y si algún
comercio tuviera un plan que no existe, **corta con un mensaje que dice cuál**
en vez de fallar con un error críptico de clave foránea.

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -f - < selfhost/postgres-init/0102_plan_empleado_digital.sql
```

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -f - < selfhost/postgres-init/0103_veredicto_ia_en_la_publicacion.sql
```

```bash
docker compose -f docker-compose.prod.yml exec -T postgres   psql -U postgres -d postgres -v ON_ERROR_STOP=1   -f - < selfhost/postgres-init/0104_por_donde_entro.sql
```

### Verificar que entraron

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -c "
    select slug, nombre, precio_mes, publicaciones_mes, funciones
      from planes order by orden;
    select count(*) as cola_difusion from difusion_cola;
    select count(*) as cargos from cargos_extra;
  "
```

Tienen que salir **6 planes** (gratis, publica, destacado, pro, empleado_ia,
premium) y las dos tablas vacías.

**Y que el candado viejo se haya ido de verdad** — es lo único de esta migración
que podría quedar a medias sin dar error:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -c "
    select conname, pg_get_constraintdef(oid)
      from pg_constraint
     where conrelid = 'comercios'::regclass and contype in ('c','f')
       and pg_get_constraintdef(oid) ilike '%plan%';
  "
```

Tiene que aparecer **`comercios_plan_fkey` (FOREIGN KEY)** y **ningún CHECK**
sobre `plan`.

---

## Paso 3 — Recargar PostgREST

Las tablas nuevas no existen para la API hasta que relea el esquema. **Si se
saltea este paso, el panel muestra errores raros sobre tablas que sí están.**

```bash
docker compose -f docker-compose.prod.yml restart postgrest
```

---

## Paso 4 — El `.env`

Antes de levantar. Editá `/docker/uruku/backend/.env` y dejá:

```
WA_NUMEROS_PROPIOS=59164610187,59167991916,59168727944,59175314737,59168727584
WA_NUMEROS_GRUPO=
WA_NUMEROS_EXPLORADOR=59168727944
WA_CONTACTO_EXPLORADOR=
BOT_WHATSAPP_NUMERO=59164610187
WA_CANAL_ID=
```

Es el bloque del diseño final del 11/9 — **WAHA sólo lee y se queda en la
tablet**. Cada línea explicada en
[numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md). `BOT_WHATSAPP_NUMERO`
es el número **vinculado a WAHA**; si algún día WAHA se muda, esta línea se
muda con él.

Los tokens de Meta (Facebook, Instagram) **todavía no**: esa parte de la cola
espera y no se pierde nada.

---

## Paso 5 — Levantar

```bash
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

```bash
curl -s https://uruku.bo/version
```

El `sha` tiene que ser el del paso 1, no el del paso 0.

---

## Paso 6 — Que arrancó bien

```bash
docker compose -f docker-compose.prod.yml logs --tail 60 backend | grep -iE "startup|error|warning"
```

Buscá `config.wa_numero_invalido`: si aparece, alguno de los números del `.env`
no pasó la validación y **esa guarda quedó apagada para ese número**. Un
placeholder tipo `591XXXXXXXX` se normaliza a `591` y no da error de otra forma.

---

## Paso 7 — Mirarlo desde el panel

En `uruku.bo/admin`:

- **Difusión** — tiene que decir "Canal de WhatsApp · falta configurar",
  "Facebook · falta configurar", "Instagram · falta configurar". **Eso es lo
  correcto hoy**: todavía no pegaste las credenciales.
- **Demanda** — el informe de búsquedas. Va a estar flaco: hay 99 búsquedas
  registradas en total y buena parte es tecleo. No es un defecto.
- **WhatsApp** — abajo, "Agregar un número a los grupos". Con 0 grupos va a
  decir que no hay ninguno.

Y una verificación de que las cuotas leen la base:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -c "
    select c.plan, count(*) from comercios c where c.activo group by 1 order by 2 desc;
  "
```

Todos deberían decir `gratis`. Si aparece alguno con otro valor, ése es el que
la clave foránea dejó pasar porque existe en `planes` — está bien.

---

## Si algo sale mal

**El backend no levanta.** Los registros dicen por qué:

```bash
docker compose -f docker-compose.prod.yml logs --tail 100 backend
```

**Volver al código anterior** (el `sha` del paso 0):

```bash
git checkout <sha-viejo>
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

**Las migraciones no se revierten, y no hace falta.** Las tres sólo *agregan*:
tablas nuevas y filas nuevas. La única que toca algo existente es la 0101, y lo
que hace es **sacar** una restricción — el código viejo funciona igual sin ella,
porque nunca dependía de esa validación para nada.

Lo único que el código viejo no entiende es la columna `plan` con valores
nuevos, y hoy no hay ninguno: todos los comercios están en `gratis`.
