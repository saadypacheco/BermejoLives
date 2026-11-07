# Verificación después de cada deploy

`scripts/verificar.sh` comprueba solo todo lo que se puede revisar sin una persona y
termina con un resumen en español: **OK** / **FALLA** / **AVISO** / **SALTEADO** por cada
chequeo y un conteo final. Corre en un minuto, no rompe nada y no necesita saber programar.

## Cómo correrlo (en el VPS, desde la carpeta del compose)

```bash
# QA
cd /docker/buscadonde && DOMINIO=encontralo.store bash scripts/verificar.sh

# Producción (DOMINIO es uruku.bo por defecto)
cd /docker/uruku && bash scripts/verificar.sh
```

Opciones:

| Opción | Qué hace |
|---|---|
| `--solo-web` | Sólo lo que se ve desde afuera (curl). Es lo que corre solo en una PC sin Docker; en el VPS no hace falta. |
| `--con-bloqueo` | Suma la prueba del bloqueo del login del panel (ver abajo). Es opcional. |
| `COMMIT_ESPERADO=abc1234` | Compara contra ese commit en vez del `git rev-parse --short HEAD` de la carpeta. |

Si no hay Docker (o no es el VPS), los chequeos internos se saltean solos con «SALTEADO: motivo».
El script termina con código 0 si no hay FALLAS y 1 si hay alguna.

## Qué NO hace

No escribe datos reales, no manda WhatsApp, no llama a Gemini/OpenAI ni publica en redes, y no
imprime ningún valor de los `.env` (sólo largo o presencia). Las pruebas de permisos de la base
se hacen dentro de una transacción que se deshace. Los pedidos de medición (`/collect`, `/lead`)
van a una ruta interna y a un comercio que no existe: no dejan visitas ni contactos.

`--con-bloqueo` es lo único que escribe algo: 6 intentos de login con un correo inventado
(`verificar-<azar>@example.invalid`) dejan 6 filas de «intento fallido» en `clave_fallos`. No toca
cuentas reales. Ojo: cuenta contra el límite de **20 fallos por hora por IP** del panel; no lo
corras más de dos o tres veces por hora desde el mismo VPS.

## Qué significa cada chequeo

1. **Contenedores:** frontend, backend, postgres, postgrest, waha y tiles están corriendo y
   sanos (reels es opcional: sólo en producción).
2. **Versión:** `/version` y `api/health` contestan, corren el **mismo commit** que el repositorio
   y el backend ve la base. Si difieren, falta un build o un `git pull`.
3. **Páginas públicas:** las pantallas principales dan 200 (no «Muy pronto», que sería el modo captura);
   la búsqueda de «farmacia» trae resultados ya en el HTML; una ficha real abre; `robots.txt` y
   `sitemap.xml` están bien para el ambiente (producción: se indexa y el sitemap tiene más de 1000
   direcciones; QA: no se indexa y el sitemap sale casi vacío).
4. **Mapa:** `tiles.<dominio>` devuelve una imagen.
5. **Seguridad:** la base (`db.`) y WAHA no se ven desde internet; ningún contenedor publica
   puertos fuera de `127.0.0.1`; un usuario anónimo **no** puede escribir en `visitas`, `leads`,
   `site_events` ni leer `leads` ni los correos de comercios; la home trae los encabezados de
   seguridad; el JavaScript del navegador no trae `rest/v1`, ninguna clave JWT ni la anon key real;
   (opcional) el login del panel bloquea al 6.º intento.
6. **Medición:** `/collect` contesta 204, `measurement-config` dice `internal:true` y `/lead` con un
   comercio inexistente contesta `{ok:false}` (si guardara una fila, se «envenena» el lote de leads).
7. **Planes:** `fotos_max` = gratis 0 · publica 60 · destacado 130 · pro 310 · empleado_ia 510, y
   el plan gratis ya no dice «Después seguís».
8. **Migraciones:** para cada archivo de `supabase/migrations/` desde la 0180 se sacan las tablas,
   vistas, funciones y columnas que crea y se comprueba que existan; si falta algo dice **qué
   migración** falta. Se arma sola: las migraciones nuevas entran sin tocar el script.
9. **Interruptores de costo:** muestra el estado de `cost_switches`. Todo apagado = OK; algo
   encendido = AVISO (gasta plata: confirmá que es a propósito).
10. **WhatsApp:** la sesión de WAHA tiene que estar en `WORKING`. Si no, no entra ninguna oferta.
11. **Workers:** muestra si `DIFUSION_WORKER`, `INDEXNOW_WORKER`, `IA_REVISION_WORKER` e
    `INTEGRACION_DIFUSION` (y los de contenido) están en true/false y de dónde sale el valor
    (`env` = escrito en el `.env`, `defecto` = el que trae el código). No juzga: compará con lo que querés.
12. **Disco y memoria:** AVISO si el disco pasa del 85 % o la memoria disponible baja de 1000 MB.

## Cuando algo da FALLA

1. No lo arregles a ciegas ni vuelvas a deployar sólo por probar.
2. Copiá **toda** la salida (de «Verificación de URUKU» hasta el resumen) y mandásela a Claude.
3. Si el FALLA es «no responde» o código 502/404 justo después de un deploy, esperá un minuto y
   volvé a correrlo: Traefik tarda unos segundos en registrar el contenedor nuevo.

Un AVISO no es una falla: es algo para mirar con calma (disco lleno, un interruptor encendido…).
