-- Los rubros nuevos de la 0057 no descongestionaron: duplicaron.
--
-- Se crearon `lenceria`, `marroquineria` y `blanqueria` para partir tres rubros
-- que no filtraban (`ropa` tenía 110 comercios). Se les dio su vocabulario, pero
-- NO se les sacó ese vocabulario a los rubros de los que se desprendían. El
-- patrón de `hogar` sigue siendo, palabra por palabra:
--
--     sabana|toalla|colcha|cortina|almohada|mantel|acolchado|frazada|blanqueria
--
-- que es el de `blanqueria`. Lo mismo `bolsos` contra `marroquineria` y `ropa`,
-- que todavía tiene `lenceria` y `bombacha` adentro.
--
-- El resultado medido (supabase/auditar_diccionario.sql, 273 comercios): cada
-- blanquería dispara hogar, cada marroquinería dispara bolsos, y esos tres
-- rubros nuevos concentran 244 de las 338 propuestas de completar_rubros.py.
-- Aplicado tal cual, `lenceria` quedaría con 102 comercios de 273 — el mismo
-- filtro que no filtra que se quiso arreglar.
--
-- Partir un rubro es MOVER el vocabulario, no copiarlo. Si el término se queda
-- en los dos lados, el comercio aparece en los dos y el comprador vuelve a
-- tener que adivinar cuál tocar.
--
-- Se borra la fila entera y se inserta la versión angosta: `rubro_palabras`
-- guarda cada patrón como una alternancia sola, así que no hay forma de sacar
-- un término sin reescribir la fila.

-- ── 1. hogar pierde el textil, que ahora es blanqueria ──────────────────────
-- Le queda lo que blanqueria no cubre: decoración y lo que va en la casa sin
-- ser ropa de cama.
delete from rubro_palabras
 where rubro_slug = 'hogar' and patron like '%acolchado%';

insert into rubro_palabras (rubro_slug, patron) values
  ('hogar', '\m(decoracion|adorno de pared|portarretrato|florero|espejo|alfombra|jarron|deco\M)')
on conflict (rubro_slug, patron) do nothing;

-- ── 2. bolsos pierde la marroquinería ───────────────────────────────────────
-- Un bolso y una mochila se llevan al hombro todos los días; una valija y un
-- maletín son otra compra y otro local. Era el argumento de la 0057.
delete from rubro_palabras
 where rubro_slug = 'bolsos' and patron like '%mochila%';

insert into rubro_palabras (rubro_slug, patron) values
  ('bolsos', '\m(bolso|mochila|bolsito|cangurera)')
on conflict (rubro_slug, patron) do nothing;

-- ── 3. ropa pierde la ropa interior, y se arregla `calza` ───────────────────
-- Dos cosas en la misma fila:
--
--   `lenceria` y `bombacha` se van: ese es el rubro nuevo.
--
--   `calza` estaba SIN cierre de palabra, así que matcheaba "calzado" — por eso
--   "CALZADOS" y "Herramienta total grumac" figuran como propuestas de ropa,
--   con el fragmento "calza" a la vista en el informe. Va `calza\M` (calza,
--   y "calzas" entra por el plural explícito).
delete from rubro_palabras
 where rubro_slug = 'ropa' and patron like '%indumentaria%';

insert into rubro_palabras (rubro_slug, patron) values
  ('ropa', '\m(ropa|vestido|pantalon|camisa|remera|polera|buzo|campera|jean|blusa|pollera|falda|short|chomba|calza\M|calzas\M|indumentaria|boutique|pijama|uniforme)')
on conflict (rubro_slug, patron) do nothing;

-- ── 4. Falsos positivos confirmados por el fragmento que los disparó ────────
--
-- Cada uno salió del informe con la palabra a la vista, no de una impresión.

-- `pastilla` mandaba a FARMACIA un kiosco que vende pastillas de menta. Una
-- farmacia se reconoce por lo demás; la palabra sola es de dos rubros distintos
-- y el error acá es caro: alguien busca un remedio y le aparece un kiosco.
delete from rubro_palabras
 where rubro_slug = 'farmacia' and patron like '%analgesico%';

insert into rubro_palabras (rubro_slug, patron) values
  ('farmacia', '\m(farmacia|medicamento|remedio|botica|analgesico|jarabe|antibiotico|ibuprofeno|paracetamol)')
on conflict (rubro_slug, patron) do nothing;

-- `sanitario` mandaba a FERRETERÍA al mismo kiosco, por el papel sanitario. En
-- una ferretería la palabra viene siempre acompañada ("artefacto sanitario",
-- "sanitarios"), y sin eso engancha limpieza e higiene femenina.
-- El resto del patrón queda igual: `pintura`, `foco` y `led` proponen 4 casos
-- que hay que mirar con el texto completo antes de tocarlos — uno es
-- "Perfumería Arabia", los otros pueden ser ferreterías de verdad.
delete from rubro_palabras
 where rubro_slug = 'ferreteria' and patron like '%griferia%';

insert into rubro_palabras (rubro_slug, patron) values
  ('ferreteria', '\m(ferreteria|herramienta|tornillo|clavo|pintura|cemento|caño|cano|electricidad|cable|foco|luces|iluminacion|lampara|led\M|construccion|taladro|martillo|alambre|griferia|pvc|artefacto sanitario|sanitarios\M)')
on conflict (rubro_slug, patron) do nothing;

-- `bateria` sin auto adelante son las pilas del bazar. Proponía repuestos de
-- auto para BAZAR LIDIA y COMERCIAL MARISOL.
delete from rubro_palabras
 where rubro_slug = 'repuestos-autos' and patron like '%amortiguador%';

insert into rubro_palabras (rubro_slug, patron) values
  ('repuestos-autos', '\m(repuesto|filtro de aceite|filtro de aire|bateria de auto|bateria para auto|amortiguador|automotor|autoparte|bujia|correa de distribucion)')
on conflict (rubro_slug, patron) do nothing;

-- `americana` suelta no nombra nada: entra por "saco americana", por un café y
-- por cualquier marca. La ropa usada se dice de las otras tres formas.
delete from rubro_palabras
 where rubro_slug = 'ropa-americana' and patron like '%fardo%';

insert into rubro_palabras (rubro_slug, patron) values
  ('ropa-americana', '\m(ropa americana|fardo|ropa usada|ropa de fardo)')
on conflict (rubro_slug, patron) do nothing;

-- `gomita` son las de pelo tan seguido como las de comer. Entró un local
-- llamado CARTERAS. Al kiosco le quedan diez palabras que sí lo nombran.
delete from rubro_palabras
 where rubro_slug = 'kiosco' and patron = '\mgomita';

-- ── 5. El courier que no se clasificaba ─────────────────────────────────────
-- FedEx está cargado (CCR3) y el patrón de `envios` no matcheaba NADA: el
-- informe lo listaba como propuesta de marroquinería, por "morral". El único
-- courier de la base clasificado como talabartería.
insert into rubro_palabras (rubro_slug, patron) values
  ('envios', '\m(fedex|dhl|encomienda|courier|paqueteria|casilla postal|giro de dinero|mensajeria)')
on conflict (rubro_slug, patron) do nothing;
