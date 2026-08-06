# ADR-027 — Interfaz del rol ejecutor: Agent Client Protocol (ACP)

Fecha: 2026-08-06
Estado: **En progreso** (idea en desarrollo, no una decisión cerrada — segunda ADR del repo con ese estado, junto a ADR-025)

> **Advertencia de estado.** Este documento registra una dirección técnica que se está discutiendo en el momento de escribirlo, para que no se pierda el razonamiento ni las fuentes verificadas. **No es la decisión definitiva.** Se espera cerrarla en breve, y hasta entonces nada de acá debe tratarse como acordado ni usarse para justificar código.

## Contexto

ADR-024 fijó que el rol ejecutor de la sala es Claude Code, y ADR-025 diseñó el puente de permisos sobre `can_use_tool` del Claude Agent SDK. Al planificar la implementación surgió una pregunta de Fernando: si Claude Code puede trabajar con modelos que no sean de Anthropic.

Verificado contra la documentación oficial de Claude Code (`code.claude.com/docs/en/third-party-integrations`): **no**. Todas las vías de despliegue son modelos Claude — Anthropic directo, Amazon Bedrock, Google Cloud Agent Platform, Microsoft Foundry, Claude Platform on AWS. Lo que esa documentación llama "LLM Gateway" (`ANTHROPIC_BASE_URL` y variantes) sirve para centralizar autenticación, límites de tasa y seguimiento de costos, no para cambiar de familia de modelo; las variables de pineado son `ANTHROPIC_DEFAULT_OPUS_MODEL`, `SONNET`, `HAIKU` y `FABLE`, todas Claude.

Eso choca de frente con el principio de ADR-012 (independencia de proveedor) y con la posición expresada por Fernando de no quedar atado a ninguna empresa. ADR-012 ya resolvió ese problema para el **modelo**, dejando el SDK detrás de una interfaz interna propia (`orchestrator.run(...)`). El **ejecutor** no tiene equivalente: entraría acoplado.

## Dirección encaminada

**La interfaz del rol ejecutor debería ser el Agent Client Protocol (ACP), no un envoltorio propio.**

ACP es un estándar abierto que hace para los agentes de código lo que LSP hizo para los servidores de lenguaje. Verbatim de su documentación oficial: *"ACP solves this by providing a standardized protocol for agent-editor communication, similar to how the Language Server Protocol (LSP) standardized language server integration"*, y nombra explícitamente el problema que motivó esta ADR: *"Developer lock-in: choosing an agent often means accepting their available interfaces."*

Existen adaptadores ACP publicados para Claude Code (`claude-agent-acp`), Codex (`codex-acp`), Amp (`amp-acp`) y Pi (`pi-acp`), más un registro de agentes que implementan el protocolo. Un agente nuevo que hable ACP entraría sin tocar la sala.

Consecuencia directa sobre la sala: el selector de ejecutor y modelo por iteración se vuelve viable con tres ejes independientes — qué agente ACP, qué modelo, y con qué modo de permisos. **Pendiente (Fase 3):** nada de esto está implementado; la sala todavía no tiene ni el consumer de navegador.

## Alternativas evaluadas

- **OpenHands** (MIT, SDK Python nativo, modelos vía convención LiteLLM): descartado como interfaz principal. Su propia documentación advierte *"No hard-deny at the analyzer boundary"* — sus analizadores de seguridad clasifican riesgo pero no bloquean — y su modo headless *"always approves"*. Frente al hook `PreToolUse` de ADR-007, que aborta de forma determinista, sería un retroceso en garantías. Detrás hay además una empresa comercial: MIT protege del bloqueo legal, no de que la dirección del proyecto siga intereses de producto.
- **Goose como interfaz** (Apache 2.0, gobernanza de la Agentic AI Foundation): no descartado, pero no es la interfaz. Goose es una implementación que ya habla ACP y expone `goose serve` con endpoint `/acp` sobre TLS. Sirve como implementación de referencia y candidato de uso, no como dependencia obligatoria. Adoptar Goose *en vez de* ACP sería cambiar una dependencia por otra.
- **Envoltorio propio del ejecutor** (una interfaz interna nuestra, al estilo de `orchestrator.run(...)` de ADR-012): descartado mientras exista ACP. Escribir un protocolo propio cuando ya hay un estándar con adaptadores publicados es trabajo que después habría que mantener y reconciliar.

## Advertencias verificadas

Ninguna de estas es motivo para descartar la dirección, pero todas deben pesar en la decisión final:

- **ACP remoto está incompleto.** Su documentación dice: *"Full support for remote agents is a work in progress."* Lo maduro hoy es el modo local, como subproceso por stdio con JSON-RPC. Para proyectos externos (ADR-025 §9) esto importa y hay que reevaluarlo.
- **La integración de Goose con Claude Code por CLI está deprecada.** Su documentación marca los providers `claude-code`, `codex` y `gemini-cli` como *"kept for backward compatibility only"*, reemplazados por los providers ACP. Cualquier diseño que se apoye en la vía CLI nace obsoleto.
- **Los providers ACP de Goose todavía no soportan reanudar ni bifurcar sesión**, según su propia documentación de limitaciones. Choca con el modelo de sesiones de ADR-025 punto 7 y hay que verificarlo antes de comprometerse.
- **Cada adaptador exige su CLI instalado y autenticado** en la máquina donde corre. No elimina la dependencia de cada proveedor: la vuelve intercambiable.

## Abierto, no resuelto

- Si el modelo de permisos de ACP conserva las garantías que hoy dan `.claude/settings.json` y el hook de ADR-007 — sin verificar.
- Si conviene que IA CENTRAL hable ACP directamente o a través de una implementación como Goose — sin decidir.
- Qué pasa con `can_use_tool` de ADR-025 punto 1 si el ejecutor deja de ser el Claude Agent SDK — sin reevaluar.
- Si el rol planificador sigue el mismo camino o queda en el orquestador propio de ADR-012 — no discutido todavía.
