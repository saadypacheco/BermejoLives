# Saber local de Bermejo para Dax (comprador)

> Investigado el 21/10/2026. Datos en `backend/data/saber_local/bermejo.json` (75 entradas: 38 `verificado: true`, 37 `false`). Sin precios de planes ni cantidades de comercios. Las cifras de cotización no se cargan (cambian a diario; las muestra el sitio).

## Qué cubre

frontera (cruce, chalanas, aduana, feriados argentinos) · cambio · pagos · compras (cómo buscar en URUKU zapatillas, ropa, por mayor, electrónica, etc.) · servicios (baños, wifi, chip, farmacias de turno, feriados bolivianos) · salud (emergencias) · seguridad · transporte · uruku (encargos y guardería, responsabilidad, WhatsApp 67 671 888, guía).

`verificado: true` = fuente oficial (ARCA, DS 5521, Min. Salud, argentina.travel) o del repo, de 2026. Todo lo que viene de prensa, guías de vendedores o es anterior a 2026 va en `false`.

## Para que el dueño confirme (`verificado: false`)

**Frontera**
- Puente 24 h y chalanas 7–19 h: sólo prensa (Todo Jujuy 07/07 y 29/09/2026). No hay horario oficial de Migraciones/Aduana de ninguno de los dos lados (la página del Min. Interior dio 403). ¿Cuál es el horario real de Migraciones y Aduana en el puente?
- Precio de la chalana: la prensa de 2026 dice 2.000 a 10.000 pesos. ¿Cuánto es hoy, ida y vuelta, con y sin mercadería?
- Multas de Bolivia a argentinos que cruzan en chalana sin que quede registrado el ingreso (hasta 100 UFV, unos Bs 300; 3 años sin entrar si no pagan; Todo Jujuy 23/01/2026). ¿La chalana registra el ingreso en Migraciones cuando funciona normal? Esto cambia cómo se recomienda cruzar.
- Documentos y menores: no hay requisito oficial publicado. Confirmar con Migración Bolivia.
- Auto/moto: no se sabe qué piden. Confirmar.
- Aduana Nacional (Bolivia) en Puerto Chalanas 6 a 18 h: nota oficial pero de 2022.
- Régimen de viajeros de Bolivia (USD 1.000): sin confirmar en 2026 en aduana.gob.bo.
- Celular y notebook/tablet sin impuestos: sale de la RG 4315/2018; la página actual de ARCA no lo menciona.
- Qué no pasa por la aduana argentina, cubiertas restringidas, SENASA, tickets: base repo (0110) y prensa; falta ARCA/SENASA.
- Decomisos y refuerzo de controles de abril 2026 (Aduana Nacional): sólo prensa.
- Fines de semana largos con filas y picos de 20.000 cruces: prensa. Fechas de feriados argentinos: oficiales.
- Calendario de feriados 2027 (1 de enero): no existe todavía en las fuentes.

**Cambio y pagos**
- Cambistas (zona del puente, puerto, centro) y que dan más que las casas: sin confirmar.
- «Casi todos aceptan pesos»: es decisión del dueño (memoria mapa-roadmap) y prensa 2025. ¿Se mantiene?
- Transferencia/Mercado Pago, tarjetas argentinas y cajeros que acepten tarjeta argentina: no se encontró nada. Dax dice «no lo tenemos confirmado».
- Dólares rinden más que pesos: consejo de prensa 2025.

**Compras y horarios**
- Qué conviene comprar (prensa jun/mar 2026). Docena vs. unidad. Mayorista desde las 5 h y cierre desde la 1 de la tarde. Siesta: no hay dato. ¿Los nombres de la avenida, la feria y las galerías? Siguen sin cargarse (nadie los publica).
- «Los mayoristas mandan por encomienda a Orán, Salta y Jujuy» y «paga la misma aduana»: viene de 0110, sin fuente.

**Servicios y salud**
- Chips Entel/Tigo/Viva: sólo guías de vendedores de eSIM; no hay página oficial de los operadores, ni precios. Roaming de líneas argentinas: sin datos.
- Emergencias: 168 está en la nota del Ministerio de Salud del 16/08/2025 (Tarija). 110 y 119 sólo en 0110 y Wikipedia; 118 aparece como ambulancia en Wikipedia. Confirmar los tres con Policía/Bomberos de Bermejo.
- Hospital de Bermejo: no se encontró nombre, dirección ni horario. Dax lo dice honestamente. ¿Cuál es y qué atiende?
- Bancos y cajeros reales de Bermejo: no se pudo listar (el mapa de URUKU solo muestra los cargados).

**Transporte**
- Tarija–Bermejo (tiempos 3 a 5 h; precios y horarios), Salta/Orán–Aguas Blancas (empresas, remises, tarifas), terminal de Aguas Blancas: fuentes agregadoras.

## Lo que ya estaba cargado y conviene actualizar

Las 9 preguntas del JSON con el mismo texto que en la base reemplazan a las viejas (el `not exists` de las migraciones las salteaba, hay que hacer UPDATE desde Admin › Ayuda): «¿Cuánto puedo llevar de vuelta…», «¿Cuánto puedo traer a Bolivia…», «¿Cómo llego a Bermejo desde Tarija?», «¿Cómo llego desde Salta u Orán?», «¿Qué conviene comprar…», «¿Se compra por unidad o por docena?», «¿Es seguro…», «¿Cómo tengo internet…» y «¿A quién llamo en una emergencia…».

- **0107, cruce** («dos formas… de 7 a 18»): las chalanas son de 7 a 19 en la prensa 2026, y presentarlas como alternativa equivalente al puente omite las multas de enero 2026. Reemplazar por las entradas nuevas de puente/chalana/multa.
- **0106 «¿Cómo cruzo a Argentina?» y 0107 «¿Cómo cruzo de Aguas Blancas a Bermejo?»**: duplicadas; unificar.
- **0107 y 0110, franquicia**: agregar que ARCA la define «mensual y no acumulable»; quedó bien lo de grupo familiar y el 50 %. `docs/saber-local-bermejo-compras.md` solo dice «acumulable entre el grupo familiar».
- **0106/0107, cambio** («¿Dónde cambio dólares o pesos?» y «¿Dónde cambio plata?»): duplicadas; apuntar a `uruku.bo/cambio` además del mapa.
- **0110, chip**: falta Viva; precios 20–50 Bs y «kioscos» sin fuente.
- **0110, emergencias**: agregar que 168 es el oficial de salud y que 118 aparece en otras listas.
- **0107, aduana boliviana** («Aduana atiende de 6 a 18 en el puerto»): es de 2022.
- **Mapeo a la base**: el JSON usa `palabras` (= `etiquetas`) y `tema`; la tabla usa `seccion` (aduana, documentos, frontera, comercios, transporte, seguridad, conectividad). No hay script de carga; los `tema` no son 1 a 1 con `seccion`.

## Alertas del repo que tocan estas entradas

- El servicio de encargos/guardería está sólo como **spec «para validar con el dueño»** (`docs/servicio-encargos-guarderia.md`): no existe `/encargos` y solo está la tarjeta de la portada que abre WhatsApp al 67 671 888. Por eso las entradas mandan al WhatsApp y no a una URL. Lo de «entregamos en Bermejo, URUKU no cruza mercadería» sale de la sección «fuera de alcance» de la spec: confirmarlo.
- `docs/legal/terminos.md` (§1 «no compra, no hace envíos»; §3 «Ninguna persona de URUKU te va a pedir plata por una compra») **contradice** el servicio nuevo hasta que se aplique la reforma de la spec (§8.1). Las entradas ya dicen «salvo nuestro servicio propio» y no repiten esa frase.
- El filtro `?modalidad=mayorista` está en `buscar-client.tsx` (lee el parámetro), pero conviene probar en la web que el filtro aparezca y funcione con `rubro=ropa`.
