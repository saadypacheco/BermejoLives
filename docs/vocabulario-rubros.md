# Vocabulario de rubros — qué escribir en la descripción

Guía de campo. El buscador de URUKU encuentra un comercio por su **nombre**, su
**descripción** y el **nombre de sus rubros**. En la calle no se puede elegir
rubro de una lista de 42, así que el rubro se infiere después a partir de lo que
el agente escribió. Este documento dice qué palabras disparan cada rubro.

## Las tres reglas

1. **Lista de productos, no una frase.** El clasificador y el buscador trabajan
   con sustantivos concretos.
   - Sirve: *"Zapatillas, championes, chinelas, mochilas escolares"*
   - No sirve: *"Tienda de artículos varios para toda la familia"*
2. **Nombrá 4 o 5 productos, los más distintos entre sí.** Si el local vende
   neumáticos, zapatillas y televisores, poné los tres: queda en los tres rubros
   y aparece en las tres búsquedas.
3. **Usá la palabra del cliente, no la técnica.** "Gomas" antes que
   "neumáticos". Si una palabra falta, se agrega a `rubro_palabras` — es una
   tabla, no código.

El **nombre del local también cuenta**: "Ferretería Roque" ya trae medio rubro
puesto.

## Tabla

| Rubro | Palabras que lo disparan | Descripción de ejemplo |
|---|---|---|
| 👕 Moda y ropa | ropa, vestido, pantalón, camisa, remera, polera, buzo, campera, jean, blusa, pollera, short, indumentaria, boutique, lencería, pijama, uniforme | "Ropa de mujer, vestidos, blusas, pantalones y camperas" |
| 👟 Calzado | zapato, zapatilla, calzado, sandalia, botín, bota, ojota, chinela, mocasín, championes | "Zapatillas deportivas, championes, chinelas y sandalias" |
| 🎒 Bolsos y accesorios | bolso, mochila, cartera, valija, maleta, billetera, morral, riñonera | "Mochilas, carteras, bolsos de viaje y billeteras" |
| 💍 Joyería y relojes | joya, joyería, reloj, anillo, collar, aro, pulsera, bijou, bisutería, alhaja | "Relojes, anillos, cadenas y bijouterie" |
| 💄 Perfumería y belleza | perfume, perfumería, cosmético, maquillaje, shampoo, belleza, esmalte, tintura, labial | "Perfumes, maquillaje, shampoo y cremas" |
| 👓 Óptica | óptica, anteojo, gafas, lentes | "Anteojos de sol, lentes recetados y armazones" |
| 📱 Celulares y accesorios | celular, smartphone, cell, funda, cargador, chip, telefonía, móvil | "Celulares, fundas, cargadores y chips" |
| 💻 Tecnología y computación | computadora, computación, notebook, laptop, impresora, informática, cartucho, tóner, pc | "Notebooks, impresoras, cartuchos y accesorios de PC" |
| 📺 TV, audio y electrónica | televisor, tv, parlante, audio, sonido, auricular, electrónica, equipo de música, dvd | "Televisores, parlantes, equipos de audio y auriculares" |
| 🔌 Electrodomésticos | heladera, refrigerador, microondas, licuadora, lavarropas, ventilador, freezer, batidora | "Heladeras, licuadoras, microondas y ventiladores" |
| 🍳 Bazar y cocina | bazar, olla, sartén, vajilla, plato, taza, cubierto, utensilio, tupper, termo, cacerola | "Ollas, sartenes, vajilla, cubiertos y termos" |
| 🛏️ Hogar y decoración | sábana, toalla, colcha, cortina, almohada, mantel, decoración, acolchado, frazada | "Sábanas, toallas, cortinas y acolchados" |
| 🛋️ Muebles y colchones | mueble, colchón, sillón, ropero, placard, cómoda, sommier | "Colchones, roperos, sillones y mesas" |
| 🔧 Ferretería y construcción | ferretería, herramienta, tornillo, clavo, pintura, cemento, caño, electricidad, cable, foco, luces, iluminación, lámpara, led, taladro, martillo, alambre, grifería, pvc | "Tornillos, pintura, cables, focos, herramientas y caños" |
| 🚗 Repuestos para autos | repuesto, filtro, batería, amortiguador, automotor, autoparte | "Filtros, baterías, amortiguadores y repuestos" |
| 🛞 Neumáticos y lubricantes | neumático, cubierta, llanta, lubricante, aceite de motor | "Neumáticos, cubiertas, llantas y lubricantes" |
| 🏍️ Motos y accesorios | moto, motocicleta, casco | "Repuestos de moto, cascos y accesorios" |
| 🚲 Bicicletas | bicicleta, bici, ciclismo, rodado | "Bicicletas, repuestos y accesorios de ciclismo" |
| 🛒 Supermercado y alimentos | supermercado, almacén, abarrote, arroz, azúcar, fideo, mercadería, comestible, verdulería, carnicería, fruta, verdura, pollo, carne, huevo, lácteo, queso, harina | "Arroz, fideos, aceite, azúcar y mercadería en general" |
| 🥤 Bebidas | bebida, gaseosa, cerveza, vino, jugo, licor, whisky, refresco | "Gaseosas, cervezas, vinos y jugos" |
| 💊 Farmacia y salud | farmacia, medicamento, remedio, pastilla, botica | "Medicamentos, remedios y artículos de farmacia" |
| 🐾 Mascotas | mascota, veterinaria, balanceado, alimento para perro/gato | "Alimento balanceado para perros y gatos, accesorios" |
| 🍽️ Restaurantes | restaurante, almuerzo, menú del día, parrilla, pensión, comedor, churrasco | "Almuerzos, menú del día y parrilla" |
| 🍔 Rotisería y comida rápida | hamburguesa, salteña, empanada, pizza, lomito, rotisería, sándwich, choripán, papas fritas, pollo frito, broaster | "Salteñas, empanadas, hamburguesas y pollo broaster" |
| ☕ Café, heladería y postres | cafetería, heladería, helado, postre, torta, batido, licuado, café | "Café, helados, tortas y jugos naturales" |
| 🥖 Panadería | panadería, pan, factura, masita, repostería, bizcocho | "Pan, facturas, masitas y repostería" |
| 💱 Cambio de moneda | cambio de moneda, casa de cambio, divisa, cambista | "Cambio de moneda: pesos, reales y dólares" |
| 📦 Envíos y encomiendas | encomienda, courier, paquetería, flete, envíos | "Envíos y encomiendas a todo el país" |
| 💈 Peluquería y barbería | peluquería, barbería, corte de pelo, salón de belleza, manicura, pedicura, uñas | "Cortes de pelo, barbería y manicura" |
| 🧼 Lavadero | lavadero, lavandería, lavado de ropa, lavado de auto | "Lavado y planchado de ropa" |
| 🔩 Gomería (servicio) | gomería, vulcanizadora, parche, alineación, balanceo | "Gomería: parches, alineación y balanceo" |
| 🗝️ Cerrajería | cerrajería, cerradura, copia de llave | "Copias de llaves y cerraduras" |
| 🏨 Hospedaje | hotel, hospedaje, alojamiento, residencial, hostal | "Hospedaje por día con habitaciones privadas" |
| 🧸 Juguetería, librería y escolar | juguete, juguetería, librería, escolar, cuaderno, lápiz, útiles, papelería, toy | "Juguetes, cuadernos, útiles escolares y librería" |
| 👶 Bebés y niños | bebé, pañal, cochecito, mamadera, chupete | "Ropa de bebé, pañales, cochecitos y mamaderas" |
| ⚽ Deportes y fitness | deporte, deportivo, gimnasio, fitness, pelota, fútbol, suplemento | "Ropa deportiva, pelotas y suplementos" |
| 🎉 Regalería y cotillón | regalo, regalería, cotillón, globo, souvenir, piñata, adorno | "Cotillón, globos, souvenirs y artículos para fiestas" |
| 👕 Ropa americana | ropa americana, americana, fardo, ropa usada | "Ropa americana por fardo y por prenda" |
| 👟 Calzado usado | zapatilla americana, calzado usado | "Zapatillas americanas usadas" |
| ♻️ Usados en general | usado, segunda mano, feria americana | "Artículos usados de segunda mano" |
| 🌷 Florería | florería, flor, ramo, maceta, vivero, planta ornamental | "Flores, ramos, plantas y macetas" |
| 📦 Otros | — | Se usa sólo cuando no se pudo clasificar. **No es un rubro real**: un comercio en "Otros" no aparece en ninguna búsqueda por categoría. |

## Multi-rubro

Un local puede caer en varios y **debe** hacerlo si vende cosas distintas.

> *"Neumáticos, zapatillas y televisores"*
> → 🛞 Neumáticos + 👟 Calzado + 📺 Electrónica

Aparece en las tres búsquedas. `comercio_rubros` es muchos-a-muchos y
`buscar_comercios` matchea por cualquiera de ellos.

## Las dos pasadas

**Primera** (30 segundos): ubicación, foto, y una descripción con 4-5 productos.
Nada más. El nombre real y el rubro pueden esperar.

**Segunda** (cuando el comercio se interesa): nombre real, WhatsApp, rubros
revisados a mano sobre lo que sugirió el diccionario, descripción más rica y
fotos buenas.
