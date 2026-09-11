# Uruku AI: qué de los dos documentos se adopta, y en qué orden

> Los dos documentos de análisis se escribieron **sin conocer lo que URUKU ya
> tiene construido**. Este archivo los adapta: qué se toma, qué se descarta,
> qué se reemplaza por lo que ya existe, y en qué orden conviene hacerlo.
>
> Decidido el 10/9/2026.

## La decisión de fondo, que es la mejor idea de los dos documentos

> **URUKU no necesita WhatsApp para tener agentes.**

Primero los agentes **adentro de URUKU** (sitio y PWA), y WhatsApp después, como
un canal más. Es la corrección más valiosa del segundo documento y cambia la
planificación entera.

**Por qué importa tanto:** conectar el WhatsApp de cada comercio exige ser *Tech
Provider* de Meta, con verificación de negocio, revisión de app y acceso
avanzado. Eso son **meses de trámite ajeno**, y no dependen de escribir código.
Poner eso en el camino crítico congela el producto sin que nadie pueda
destrabarlo desde acá.

Adentro de URUKU no hace falta ningún permiso de Meta. Se puede lanzar,
cobrar y aprender mientras el trámite avanza en paralelo.

## Qué se adopta tal cual

| Idea | Por qué |
|---|---|
| **Router escalonado (Nivel 0/1/2/3)** | No mandar "¿a qué hora abren?" a un modelo. Es lo más barato de construir y lo que más ahorra. |
| **Tool Layer con permisos en el backend** | La seguridad nunca puede depender del prompt. Ya es como funciona el resto del sistema. |
| **Los datos salen de la base, no del modelo** | Un precio inventado se paga en el mostrador, con un cliente que vino por eso. |
| **No mandar catálogos enteros al prompt** | Menos tokens, menos latencia, menos invención, datos frescos. |
| **Niveles de autonomía** | Recomendar / preparar / ejecutar / automatizar. Es una columna de configuración, no arquitectura. |
| **Medir el costo por comercio desde el día uno** | Sin eso no se puede saber si el plan deja margen. |
| **Multi-tenant desde el diseño** | Rehacerlo después es rehacer todo. |

**El humano del Nivel 3 es el dueño del local**, no URUKU. Es una decisión
importante: sin eso, mil comercios escalando a un humano son un equipo de
soporte que ningún plan paga.

## Qué NO se adopta

**Rehacer el backend en Node/TypeScript.** Los dos documentos lo proponen
porque no saben que existe: URUKU corre **FastAPI/Python con 621 tests**,
incluidas las reglas de atribución, cuotas, moderación y difusión. Nada del
diseño propuesto necesita Node — el mismo router, las mismas tools y las mismas
colas se escriben en Python. **Se mantiene lo que hay y se le suma
funcionalidad.**

**BullMQ + Redis para las colas, hoy.** El backend ya tiene su patrón de
trabajadores en segundo plano (`_clima_loop`, `_baja_loop`, `_difusion_loop`) y
alcanza para el volumen actual. Una cola de verdad se justifica cuando haya
picos reales, y se va a notar.

**Redis como cache, hoy.** Con 888 comercios y el tráfico de ahora, Postgres
sobra. Es correcto a la escala de los documentos, no a la de esta semana.

**El "AI Marketplace" de agentes verticales.** Buena visión, ninguna urgencia.

**WAAC / número compartido entre partners.** Aparece como una posibilidad que
reduciría mucho la fricción. **No tengo información confiable de que esté
disponible en producción, ni para Bolivia.** Hay que verificarlo antes de
planificar nada encima: una arquitectura apoyada en una función que no existe se
descubre tarde.

## Lo que los dos documentos no vieron

### El costo de dar de alta a un comercio en el plan de 1.250

Los datos que el agente necesita —catálogo, precios, stock, horarios— **se
cargan cuando el comercio contrata**. Perfecto. Pero eso significa que cada
venta arranca con **horas de carga de datos**: un local con 500 productos no se
carga solo.

A Bs 1.250 por mes, si dar de alta cuesta dos días de trabajo, el primer mes ya
se fue. Entonces:

> **El Agente Catálogo —el que carga productos desde fotos— no es una función
> más del producto: es lo que hace que el producto tenga margen.**

Conviene construirlo temprano, aunque al principio lo use sólo el equipo de
URUKU para dar de alta comercios. Y hay una ventaja escondida: es el mismo
problema que ya resuelve la ingesta de ofertas por WhatsApp (foto → datos), así
que parte del camino está hecho.

### El Agente Analista se puede construir HOY, y es el único que sí

Todos los agentes necesitan datos que todavía no existen. **Menos uno.**

Las búsquedas del sitio ya se registran, con el término y la cantidad de
resultados. O sea que esto ya es calculable:

```
Últimos 7 días
  26 búsquedas sin ningún resultado
  147 personas buscaron «zapatillas»
  0 comercios publicaron algo de eso
```

**No necesita LLM, ni Meta, ni catálogo.** Es una consulta. Y es al mismo tiempo
el mejor argumento de venta que puede tener URUKU frente a un comerciante:

> *"Veintiséis personas buscaron esto en Bermejo esta semana y no encontraron
> nada. Vos lo vendés."*

Eso no lo puede decir ningún competidor, porque nadie más tiene la demanda
medida de la ciudad.

### El plan de 1.250 tiene que traer algo que el de 400 no trae

`asistente_24_7` estaba declarado en el plan Pro (Bs 400) de una charla
anterior. Si el de 1.250 no suma ninguna función sobre aquél, no hay nada que
vender: el comerciante mira los dos y elige el barato, con razón.

Ya está corregido en la migración 0102 — la función se movió al plan nuevo. Si
la idea era que Pro también la tuviera, se le vuelve a poner desde el panel; para
eso las funciones son un objeto libre.

## El plan, ya creado

| | |
|---|---|
| Nombre | **Empleado Digital** |
| Precio | **Bs 1.250/mes** — editable desde el panel |
| Publicaciones | Sin límite |
| Funciones | `asistente_24_7`, `agente_catalogo`, `agente_analista`, `agente_marketing`, `multicanal`, `leads`, `canal_wa` |

El precio va en la base a propósito: los costos de implementación y
mantenimiento de un agente 24/7 **todavía no están medidos**, y hasta que lo
estén el precio se va a mover. Que se mueva sin un deploy.

**El tope diario del canal le sigue aplicando.** Ese tope protege a los
seguidores, no al negocio: si el plan más caro pudiera saturar el canal, el daño
lo pagan todos los demás.

## El orden recomendado

Ordenado por **valor sobre esfuerzo con los datos que hay hoy**, que no es el
orden de ninguno de los dos documentos.

1. ~~**Agente Analista (informe de demanda).**~~ ✅ **Construido el 10/9** —
   Admin › Demanda. Sin IA, con las búsquedas que ya se registran. Muestra lo
   más buscado, lo que no encontró nada, y arma la frase para decirle a un
   comerciante. Descarta el tecleo a medio escribir: sin eso el informe diría
   que lo más buscado en Bermejo es «zap».
2. ~~**IA en la ingesta**~~ ✅ **Hecho el 11/9** — la cola de moderación llega
   ordenada; el veredicto vive en la fila y no en el navegador.
3. **Nivel 0** — horario, dirección, teléfono, cómo llegar, resueltos por
   consulta directa. Sin modelo. Cubre la mayoría de las preguntas reales.
3. **Uruku Ayuda** — el asistente del propio sitio. Riesgo bajo: si se equivoca,
   se equivoca sobre URUKU, no sobre el precio de un comercio. Es donde se
   estrena el núcleo.
4. **Agente Catálogo**, primero para uso interno. Es lo que hace rentable dar de
   alta a un comercio.
5. **Uruku Chat** — el agente de la ficha del comercio, con los datos ya
   cargados por el punto anterior.
6. **Acciones** (crear oferta, cambiar precio) con confirmación y auditoría.
7. **WhatsApp**, cuando el trámite con Meta haya avanzado.

Los puntos 1 y 2 no necesitan nada que no exista. El 3 necesita un texto de
preguntas frecuentes que hay que escribir. Del 4 en adelante depende de que haya
comercios contratados con sus datos cargados.

## Lo que ya está construido y sirve de base

No hay que empezar de cero:

- **Capa de proveedores de canal** (`mensajeria.py`): WAHA o Meta con una
  variable. Es la misma forma que pide el documento para los modelos de IA.
- **Clasificador con IA** (`clasificador.py`, Gemini) y **visión**
  (`vision.py`): ya hay un proveedor de modelo integrado y probado.
- **Planes con funciones en la base**: `funcion(plan, "agente_catalogo")` ya
  responde. Los permisos por plan no hay que inventarlos.
- **Cola con estados, reintentos y pantalla** (la difusión): el patrón que va a
  necesitar cualquier agente que ejecute acciones.
- **Ingesta foto → datos**: medio Agente Catálogo, funcionando.
- **Búsquedas registradas**: los datos del Agente Analista.
