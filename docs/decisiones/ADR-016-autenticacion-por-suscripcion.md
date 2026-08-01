# ADR-016 - Fase 3 arranca con autenticación por suscripción, no con clave de API

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

Al ejecutar la verificación de punta a punta del gateway LiteLLM (ADR-012), la petición atravesó correctamente toda la cadena (`web` → `litellm` → API de Anthropic) pero la API respondió que el saldo de crédito era insuficiente. Se comprobó en `console.anthropic.com`: la organización tiene 0,00 US$ de crédito y existe una sola organización, así que no era un problema de clave asignada a la cuenta equivocada. Los 85 US$ de crédito promocional que se creían disponibles no estaban ahí — correspondían a la suscripción de claude.ai, que es un producto distinto y cuyo saldo no se comparte con la API.

Al verificar la documentación oficial antes de asumir que había que comprar créditos, se encontró que Anthropic anunció para el 15 de junio de 2026 un cambio que habría separado el uso del Agent SDK de los límites de la suscripción (con un crédito mensual propio de 20 US$ para el plan Pro), pero **pausó ese cambio**. La nota vigente dice que por ahora nada ha cambiado: el uso del Claude Agent SDK y de `claude -p` sigue consumiendo los límites de uso de la suscripción, sin clave de API y sin cargo por token.

## Decisión

Fase 3 arranca usando **autenticación por suscripción** (la del plan Pro, vía la vía OAuth de Claude Code), no con clave de API de `console.anthropic.com`. No se cargan créditos de API por ahora.

Consecuencia directa sobre ADR-012: como LiteLLM proxifica peticiones autenticadas por clave de API, **el gateway no está en el camino de las llamadas a Claude mientras se use suscripción**. Queda montado, sano y sin puerto publicado (ya commiteado), listo para cuando se enrute tráfico a través de él, pero hoy no interviene. La frontera `orchestrator.run(...)` de ADR-012 no se ve afectada — es precisamente lo que hace barato el cambio.

## Alternativas descartadas

- **Cargar crédito de API y seguir el diseño original de ADR-012 tal cual**: es la vía que deja el gateway en el camino desde el primer día y da facturación predecible. Se descarta por coste: el proyecto está en fase de desarrollo, la suscripción ya pagada cubre el uso, y no hay razón para pagar dos veces por lo mismo mientras la vía gratuita esté disponible.
- **Renunciar al gateway y quitarlo del stack**: se descarta. Ya está montado y verificado en lo que se puede verificar sin crédito, no molesta (no publica puerto, consumo despreciable), y sigue siendo necesario para el objetivo multi-IA de ARQUITECTURA.md §2 y para el momento en que la vía de suscripción deje de estar disponible.

## Consecuencias

- **El orquestador consume los mismos límites de uso que el trabajo interactivo.** Lo que gaste corriendo desatendido sale del mismo cupo del plan Pro que se usa para Claude Code en la sesión `iac` y para conversaciones en claude.ai. Un bucle mal ajustado puede dejar a Fernando sin cupo para trabajar. Hay que vigilarlo activamente durante Fase 3, sobre todo al probar corridas largas.
- **La vía es explícitamente provisional.** Anthropic declaró que está reformulando el plan y que avisará antes de que algo tenga efecto. Si se revierte, hay que pasar a clave de API — y gracias a la frontera de ADR-012 eso es un cambio de configuración, no una reescritura. Esta ADR debería revisarse en cuanto Anthropic publique el nuevo esquema.
- **La verificación de enrutado real del gateway queda pendiente indefinidamente.** No hay forma de probarla sin crédito de API, y con suscripción el gateway no está en el camino. Lo único probado hoy es que el contenedor levanta, queda `healthy` y no expone puerto (ya reflejado en CHANGELOG.md).
- Pendiente (Fase 3): confirmar en la implementación del orquestador que la autenticación por suscripción funciona efectivamente desde dentro del contenedor, y no solo desde la sesión interactiva de Claude Code.
