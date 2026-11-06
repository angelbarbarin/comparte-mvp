# Entrega del MVP

| # | Entregable | Estado | Dónde |
|---|---|---|---|
| 1 | Video de la demo con el proyecto funcionando | ⏳ Por grabar | Instrucciones en [`GUION_VIDEO.md`](GUION_VIDEO.md) |
| 2 | Entrada de texto describiendo el entregable | ✅ Borrador abajo | Sección siguiente |
| 3 | Liga al Git con código y documentación | ⏳ `REPO_URL` | Repositorio de GitHub |

## Entrada de texto (lista para pegar)

> **ComParte — MVP de la plataforma agéntica de rescate de alimentos (ODS 2: Hambre cero)**
>
> Entregamos la primera versión funcional de ComParte, construida a partir del Documento de Visión y Alcances. Un negocio donante reporta su
> excedente por chat y cuatro agentes —Captador, Coordinador, Logístico e Impacto—, coordinados por un orquestador, lo llevan hasta el receptor que
> más lo necesita, organizan quién lo recoge y miden el impacto, con una persona que valida los alimentos de riesgo.
>
> **Funcionalidad entregada**
> - **Captador:** conversa en español, estructura la donación (alimentos, cantidades, caducidad), pregunta lo que falta, pide confirmación y bloquea alcohol y alimentos en mal estado.
> - **Coordinador:** elige al receptor con un puntaje explicable (necesidad, cercanía y capacidad), guarda el motivo de cada descarte y reasigna si el receptor rechaza.
> - **Logístico:** elige al voluntario con la ruta más corta que cumpla capacidad, hielera, horarios y caducidad; el voluntario acepta, recoge y entrega.
> - **Impacto:** kg rescatados, raciones, personas beneficiadas y CO2e evitado, por alimento y por municipio.
> - **Orquestador y supervisión humana:** enruta entre agentes; carnes, lácteos y comida preparada esperan la aprobación de una persona; cada decisión queda en una bitácora visible como línea de tiempo.
> - **Interfaz web** con chat, seguimiento con mapa, consolas de receptor, voluntario y administrador, y tablero de impacto; piloto simulado de 10 donantes, 5 receptores y 5 voluntarios.
>
> **Métricas definidas:** kg rescatados; raciones (kg ÷ 0.5); personas beneficiadas (raciones ÷ 3, personas alimentadas un día completo); CO2e evitado. Son supuestos por validar con un banco de alimentos real.
>
> **Retroalimentación atendida:** canal web como plan B ante el costo de WhatsApp Business; métricas de impacto; agentes y orquestador separados y visibles. Pendiente: validar el flujo con un banco de alimentos real.
>
> **Límites:** en esta versión los agentes usan reglas, sin modelo de lenguaje; los datos son simulados; no hay fotos, autenticación ni WhatsApp; las rutas son estimadas. Verificado con 68 pruebas automáticas y un recorrido manual en el navegador.
>
> **Siguientes pasos hasta el 24 de noviembre:** incorporar un LLM al Captador, diagramas UML, video con todos los casos de uso, validación con un banco de alimentos y autenticación por roles.
>
> **Video:** `VIDEO_URL` · **Código y documentación:** `REPO_URL`

## Lista de verificación

- [ ] `pytest` pasa y el README funciona en otra computadora siguiendo solo sus instrucciones.
- [ ] El video sigue [`GUION_VIDEO.md`](GUION_VIDEO.md) y abre en una ventana de incógnito.
- [ ] Sustituyeron `VIDEO_URL` y `REPO_URL` por las ligas reales.
- [ ] El repositorio es accesible para el profesor.
- [ ] No hay claves ni datos personales en el historial (`git log -p | findstr /i "sk-ant-"` no debe encontrar nada).

## Preguntas probables

| Pregunta | Respuesta honesta |
|---|---|
| ¿Usa IA / un LLM? | En esta versión no: los agentes usan reglas y heurísticas deterministas. Incorporar un LLM al Captador es el siguiente paso |
| ¿Funciona con WhatsApp? | No, el canal es web (plan B por costo) |
| ¿Los datos son reales? | No, son ficticios |
| ¿Por qué esas métricas? | Las pidió la retroalimentación; sus factores son supuestos documentados y por validar |
| ¿Es seguro para producción? | No: sin autenticación; las reglas de inocuidad son heurísticas, no una certificación sanitaria |
