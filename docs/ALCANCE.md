# Alcance del MVP

Primera versión funcional de ComParte, pensada para **dos semanas y tres personas**. Parte del
[Documento de Visión y Alcances](Vision_y_Alcances_ComParte.docx) y de la retroalimentación del profesor.
Si este documento contradice al código, gana el código.

## Objetivo

Demostrar de punta a punta, con datos de prueba del AMG, que **un excedente reportado por un donante llega
a un receptor sin que nadie lo coordine a mano**:

```
Donante (chat) → Captador → [revisión humana si hay riesgo] → Coordinador → Logístico → Impacto
                          todo mediado por el Orquestador y registrado en una bitácora
```

## Qué incluye (y hasta dónde llega)

| Característica | Estado | Alcance en este MVP |
|---|---|---|
| CP-01 Registro conversacional | ✅ | Chat web en español; entiende cantidades, unidades, caducidad y alimento en mal estado; pregunta lo que falta y confirma antes de registrar |
| CP-02 Inocuidad | ✅ | Bloquea alcohol, medicamentos y alimentos en mal estado; carnes, lácteos y comida preparada esperan la aprobación de una persona |
| CP-03 Perfil de receptores | 🟡 | Perfil en la base (necesidades, capacidad, frío, horario). Se carga con datos de prueba; **no hay formulario de alta ni verificación de organizaciones** |
| CP-04 Asignación | ✅ | Puntaje explicable (necesidad, cercanía, capacidad), filtros con motivo y reasignación si rechaza |
| CP-05 Recolección | 🟡 | Elige voluntario y ruta; el voluntario acepta, rechaza, recoge y entrega. Voluntarios simulados |
| CP-06 Trazabilidad | ✅ | Estados de la donación, avisos al donante y bitácora de decisiones por agente |
| CP-07 Tablero de impacto | 🟡 | kg, raciones, personas y CO2e, por alimento y por municipio. **Sin gráficas históricas ni historial simulado** |
| CP-08 Reportes | ⛔ | No incluido |
| CP-09 Administración | 🟡 | Solo aprobar/rechazar alimentos de riesgo y reiniciar datos de demo |
| CP-10 Notificaciones | ⛔ | Excluida en el documento de visión para esta versión |

## Qué NO incluye (a propósito)

- **Ningún modelo de lenguaje (LLM).** Los cuatro agentes usan reglas y heurísticas deterministas: la comprensión del
  español es por expresiones regulares y un catálogo de alimentos. Es gratis, reproducible y funciona sin internet,
  pero entiende solo un subconjunto del idioma. **Sustituir `comparte/nlu.py` por un LLM es el siguiente paso**
  (misma salida: `Interpretacion`).
- Sin fotos, sin WhatsApp, sin autenticación ni roles (cualquiera "actúa como" cualquier usuario).
- Sin API de mapas: distancia = línea recta × 1.3 y 25 km/h.
- Sin tiempos límite de respuesta: una oferta espera hasta que el receptor responde.
- Una donación se asigna a un solo receptor y un solo voluntario; sin componente de equidad entre receptores.
- Sin PostgreSQL (SQLite; se cambia con `COMPARTE_DB_URL`) ni despliegue.

## Métricas definidas (pedidas por el profesor)

| Métrica | Definición | Supuesto por validar |
|---|---|---|
| kg rescatados | kg confirmados por el receptor (o los registrados) | — |
| Raciones | kg ÷ 0.5 | 0.5 kg por ración |
| Personas beneficiadas (est.) | raciones ÷ 3 = personas alimentadas un día completo | 3 raciones por persona al día |
| CO2e evitado | Σ kg × factor de cada alimento | Factores aproximados tomados de memoria, **sin verificar** |

Están en `comparte/conocimiento.py`.

## Datos de prueba

10 donantes, 5 receptores y 5 voluntarios **ficticios** (coordenadas aproximadas de colonias reales del AMG).
Cumple el piloto prometido en el documento de visión (≥ 10 donantes y ≥ 5 receptores).

## Verificación

- `pytest`: 68 pruebas (conocimiento, comprensión de lenguaje, agentes, flujos completos y API).
- Recorrido manual en el navegador integrado (Chromium): rescate completo con rechazo y reasignación, alimento de
  riesgo con aprobación humana y tablero de impacto. A 375 px de ancho **no** se probó esta versión.
- **No verificado:** Safari/Firefox, `scripts/demo.sh` (macOS/Linux), rendimiento, y cualquier cifra con datos o usuarios reales.
- La comprensión de lenguaje no se midió contra mensajes etiquetados en esta versión.

## Qué sigue

Ver el final de [`ARQUITECTURA.md`](ARQUITECTURA.md): LLM en el Captador, tiempos límite, autenticación, WhatsApp
o el canal que se decida, validación con un banco de alimentos real y los diagramas UML finales.
