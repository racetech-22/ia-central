# ADR-032 - Verificación automática de ARQUITECTURA.md §6

Fecha: 2026-08-07
Estado: Aceptada

## Contexto

CLAUDE.md exige que cada ADR nueva deje su renglón en ARQUITECTURA.md §6 en el mismo commit — el mismo hábito que ya exige para `docs/decisiones/INDEX.md` y CHANGELOG.md. De esos tres, dos tienen verificación determinista y uno no: ADR-018 puso un hook que bloquea si INDEX.md no coincide con los archivos reales, ADR-029 puso hook más test para `docs/estado.yml`, y **§6 depende de que alguien se acuerde**.

Es la misma categoría de hueco que este proyecto viene cerrando de forma explícita: una convención documentada pero no forzada por código. El precedente más cercano es el propio ADR-029, que nació porque el mapa de ruta dibujado a mano acumuló dos desvíos reales en tres días.

Dos hechos suben la prioridad, y ninguno es hipotético:

- **§6 pasó a ser piso mínimo de lectura permanente** por la enmienda del 2026-08-07 a CLAUDE.md, precisamente por ser el único índice barato de conexiones cruzadas entre decisiones — el lugar donde se detecta que algo nuevo rompe una condición de una ADR vieja.
- **Ese mecanismo pagó dos veces en la sesión del 2026-08-07**: ADR-030 encontró por §6 la línea de ADR-022/ADR-023 sobre no otorgar acceso a la API de Docker, y ADR-031 encontró que enmendaba el punto 6 de ADR-028. Si §6 se degrada en silencio, se degrada esa capacidad de detección, no un documento decorativo.

## Decisión

1. **Un comando de validación propio (`validar_arquitectura`), no bash suelto en el hook.** Motivo, literal del comentario que la validación 2 del hook ya lleva escrito: la verificación de `docs/estado.yml` se delegó a un management command "en vez de reimplementarla en bash: misma validación que corre la suite de tests, una sola fuente de verdad". Escribir esta en bash y otra vez en Python para el test crearía las dos versiones que ese comentario existe para evitar.

2. **La verificación es bidireccional**, igual que la de INDEX.md en la validación 1 del hook: falla si un archivo `docs/decisiones/ADR-NNN-*.md` no tiene renglón `- ADR-NNN:` en §6, y falla también si §6 tiene un renglón `- ADR-NNN:` sin archivo real correspondiente.

3. **Se llama desde dos lugares, no uno**, siguiendo el patrón que ADR-029 estableció:
   - **Hook de pre-commit**, con disparador propio: se activa si el commit toca `docs/decisiones/` **o** `ARQUITECTURA.md`. El segundo disparador no es adorno — §6 se puede romper editando ARQUITECTURA.md en un commit que no toca ninguna ADR, y sin ese disparador el hook no se enteraría nunca.
   - **Test en la suite**, que corre siempre: no se saltea con `--no-verify` y no depende de que el clon tenga `core.hooksPath` apuntando a `.githooks` — la activación manual por clon que ADR-029 ya identificó como frágil.

4. **CHANGELOG.md queda deliberadamente fuera de alcance.** Sus entradas son prosa sin marca fija; hacerlo verificable exigiría imponerle un formato rígido, o sea cambiar el documento para satisfacer al chequeo. §6 ya tiene formato rígido (`- ADR-NNN: `) y no hay que tocar nada para verificarlo. Es una omisión marcada, no un olvido.

## Alternativas descartadas

- **Bash dentro del hook, sin comando ni test**: descartada por el motivo del punto 1. Tiene una ventaja real que se pierde y conviene dejar registrada: hoy un commit que solo agrega una ADR no necesita Docker corriendo, y con esta decisión pasa a necesitarlo. Se acepta porque en este despliegue el contenedor `web` está siempre arriba, el hook ya prefiere `exec` sobre un contenedor corriendo antes que crear uno nuevo, y ya distingue "Docker no disponible" de "el archivo es inválido" con mensajes separados.
- **Extender `validar_estado` en vez de un comando nuevo**: descartada porque el disparador es distinto. `validar_estado` se activa por `docs/estado.yml`; esta verificación se activa por `docs/decisiones/` o `ARQUITECTURA.md`. Fundirlas obligaría a correr cada una fuera de su caso.
- **Solo el test de la suite, sin hook**: descartada porque el hook da la señal en el momento del commit, cuando el contexto está fresco y el arreglo cuesta un renglón, en vez de en la próxima corrida de tests.
- **Extender el alcance a CHANGELOG.md**: ver punto 4.

## Consecuencias

- **La tercera pata de la convención de CLAUDE.md queda forzada por código.** INDEX.md (ADR-018), `docs/estado.yml` (ADR-029) y ahora §6. De lo que CLAUDE.md exige commitear junto a una ADR nueva, solo CHANGELOG.md sigue dependiendo de la memoria de quien commitea, y por la razón del punto 4.
- **Commitear documentación pasa a requerir Docker.** Ver alternativas descartadas: costo aceptado, con la mitigación ya presente en el hook.
- **El hook gana una tercera validación.** Para no triplicar la lógica de invocación (preferir `exec` sobre `web` corriendo, caer a `run --rm`, distinguir Docker caído de validación fallida), esa maquinaria se extrae a una función de shell reutilizada por la validación de `docs/estado.yml` y por la nueva. Es una modificación a código que hoy funciona: exige que la suite quede en verde y que la validación de `estado.yml` siga bloqueando lo que bloqueaba, verificado, no supuesto.
- **La primera corrida es en sí misma una auditoría**: dice si §6 está completo para las 31 ADR existentes. Si aparece algún faltante, es un desvío real que estaba sin detectar, no un falso positivo del chequeo nuevo.
- **Encaje en `docs/estado.yml`**: se suma ADR-032 a la pieza `auditorias_automaticas`, que es la más cercana de las existentes, junto con el archivo del comando nuevo como artefacto. No es un encaje perfecto — esa pieza describe las auditorías por cron (`memory_audit.sh`, `adr_audit.sh`), no los hooks de pre-commit, que hoy no tienen pieza propia en el mapa. Queda anotado: si se suma una verificación más de esta familia, conviene darle pieza propia en vez de seguir estirando esta.
- **Construido, no pendiente.** A diferencia de ADR-030 y ADR-031 —documentación de decisiones sin una línea implementada—, esta ADR se acepta junto con su implementación y su verificación adversarial. Si la verificación no pasa, la ADR no se commitea.
