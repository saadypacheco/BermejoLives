# Preguntas abiertas — Bermejo Live Market

> Generadas en F0 (`/architect-idea`, sesión 1, 2026-06-04). Las 🔴 bloquean
> decisiones de `/architect-stack`. Resolverlas (o decidir un default explícito)
> antes de cerrar F1.

## 🔴 Bloqueantes (deciden arquitectura)

1. **Rol de FastAPI.** ¿FastAPI maneja todo el backend, o queda acotado al
   subsistema de integración (webhooks WhatsApp, jobs, publicación TikTok) mientras
   Next.js Server Actions + Supabase cubren el CRUD de la app? — *Hipótesis F0:
   FastAPI solo para integración.*

2. **Proveedor de WhatsApp Business API.** Meta Cloud API directo vs Twilio vs
   360dialog vs Gupshup. Define costo por conversación, complejidad del webhook y
   tiempo de aprobación de Meta. ¿Hay número de WhatsApp Business ya verificado?

3. **Método de publicación en TikTok.** ¿Un operador humano recibe el video por
   WhatsApp y lo sube manualmente a TikTok (y pega el link), o se automatiza con la
   **TikTok Content Posting API** (requiere app aprobada por TikTok)? — *F0 sugiere
   operador manual al inicio; API después.*

## 🟡 Importantes (afectan diseño, no bloquean arrancar)

4. **Monedas.** Frontera BO/AR: ¿se muestran precios en Bs, USD y/o ARS? ¿Conversión
   manual por el comerciante o tipo de cambio automático?

5. **Modelo de monetización.** Planes de suscripción para comercios (Gratis/Pro/
   Premium como en el prototipo) + pagos vía MercadoPago. ¿Qué desbloquea cada plan?

6. **Roles y permisos.** Confirmar set de roles: comprador (anónimo o registrado),
   comerciante, moderador, admin. ¿El comprador necesita cuenta para algo?

7. **Hosting.** ¿Vercel para Next.js + Supabase Cloud + dónde corre FastAPI (Railway/
   Fly/Render/VPS)? Considerar costo y región (latencia Bolivia).

8. **Identidad del comerciante.** ¿Alta self-service con verificación, o el equipo
   da de alta los comercios? ¿Verificación por WhatsApp (pattern KB
   identidad-celular-progresiva)?

## 🟢 Menores (se pueden diferir)

9. **Mapa isométrico.** ¿Se mantiene la versión CSS/SVG del prototipo, se ilustra a
   mano, o se hace en Three.js? Decisión de F2/diseño, no de stack.

10. **i18n.** ¿Solo español, o se prevé inglés/portugués por la frontera/turismo?

11. **Destino del prototipo estático.** ¿Se mueve a `/prototype`, se borra tras
    portar el diseño, o se conserva en la raíz como referencia?

12. **Moderación.** ¿Cuántos moderadores? ¿SLA de aprobación? ¿Notificación al
    comerciante cuando se aprueba/rechaza (por WhatsApp)?
