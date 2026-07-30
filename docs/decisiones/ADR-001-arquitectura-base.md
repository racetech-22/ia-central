# ADR-001 - Arquitectura en tres capas y principio de portabilidad/verificación

Fecha: 2026-07-30
Estado: Aceptada

## Contexto

IA CENTRAL debe servir para desarrollar, administrar y modificar todos los proyectos de Fernando (locales y en múltiples servidores), explotar tanto IAs open source como de pago, y auto-aprender de las conversaciones con las IAs conectadas, pero ese aprendizaje debe ser siempre comprobable como real, no ruido acumulado. Además, el sistema debe poder transferirse completo a otro servidor si es necesario.

## Decisión

Se adopta una arquitectura de tres capas separadas:

1. Orquestación (Claude Agent SDK): decide qué hacer y a quién delegar.
2. Conocimiento (base vectorial + documentos versionados en Git): memoria de largo plazo, independiente del servidor físico.
3. Ejecución (conectores MCP, Claude Code, router de modelos): el brazo que actúa sobre proyectos, servidores y otras IAs.

Se adopta también un pipeline obligatorio para todo conocimiento auto-generado: captura, verificación, promoción. Nada se trata como "conocimiento confirmado" sin pasar por verificación (cruce de fuentes o confirmación explícita de Fernando).

## Alternativas descartadas

- Agente monolítico sin capas separadas: más rápido de prototipar, pero acopla memoria a un servidor específico y dificulta la portabilidad exigida desde el inicio. Descartado.
- Auto-aprendizaje sin pipeline de verificación: cumple el requisito de "aprender solo", pero arriesga acumular información falsa o desactualizada con el tiempo. Descartado.

## Consecuencias

- La capa de conocimiento debe diseñarse desde el inicio como exportable/restaurable (dumps versionados), no como archivos sueltos en el servidor de orquestación.
- Toda función de auto-aprendizaje debe implementar las tres etapas del pipeline antes de considerarse completa.
