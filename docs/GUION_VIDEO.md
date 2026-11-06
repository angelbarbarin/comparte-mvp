# Guion e instrucciones para grabar el video de la demo

Duración objetivo: **6 minutos** (máximo 8). Lo que se hace y se ve en pantalla fue **verificado contra la aplicación real**
(hora de demo 16:00 y datos recién cargados). El número de donación y la hora mostrados pueden variar.

## 1. Qué pide la entrega

(1) **Video** de la demo describiendo la funcionalidad, (2) **entrada de texto** ([`ENTREGA.md`](ENTREGA.md)) y (3) **liga al Git**.
Este guion cubre el (1).

## 2. Antes de grabar (15 minutos)

- [ ] Estás en la última versión de `main` y `pytest` pasa.
- [ ] Cerraste correo, chats y notificaciones. Navegador en pantalla completa (F11), zoom 100–110 %, sin marcadores visibles.
- [ ] Micrófono probado. Tienes internet (si no, el mapa se ve sin mosaicos; el resto funciona).

**Arranque limpio** (cada vez que repitas la grabación completa):

```powershell
.\scripts\demo.ps1
```

Abre <http://127.0.0.1:8000>. Arriba a la derecha debe decir *Hora de demo: 16:00* y *Datos de demostración*.
Si algo queda a medias: pestaña **Operación → Reiniciar datos de demo** y F5.

**Grabar en Windows:** Xbox Game Bar (`Win + Alt + R` inicia y detiene) u [OBS Studio](https://obsproject.com/). Graba por escenas;
si te equivocas, repites solo esa. **Haz una prueba completa antes de grabar de verdad.**

## 3. Escenas y tiempos

| # | Escena | Pestaña | Tiempo |
|---|---|---|---|
| 0 | Introducción | cualquiera | 0:40 |
| 1 | Un donante registra su excedente por chat | Donar | 1:00 |
| 2 | Cómo decidieron los agentes | Seguimiento | 1:00 |
| 3 | El receptor rechaza y se reasigna; el voluntario recoge y entrega | Operación | 1:15 |
| 4 | Confirmación e impacto | Operación / Impacto | 0:50 |
| 5 | Alimento de riesgo y revisión humana; alimento no aceptado | Donar / Operación | 0:55 |
| 6 | Cierre honesto | — | 0:30 |

## 4. Guion

> Los textos de **Decir** son sugerencias; háganlos suyos.

### Escena 0 · Introducción
**Decir:** "En México se desperdician millones de toneladas de alimentos mientras casi 1 de cada 5 personas tiene carencia por
acceso a la alimentación. Mucho excedente sale de panaderías y mercados dispuestos a donar, pero coordinarlo a mano es lento.
ComParte es un sistema de cuatro agentes coordinados por un orquestador: recibe la donación por chat, elige al receptor que más
la necesita, organiza quién la recoge y mide el impacto. Les mostramos el MVP con datos de prueba del Área Metropolitana de Guadalajara."

### Escena 1 · Registrar una donación (Donar)
**Hacer:**
1. Pestaña **Donar** (donante por defecto: *Panadería La Espiga · Tlaquepaque*).
2. Pulsa el ejemplo **“Pan del día y fruta”** (*Tengo 25 kg de pan dulce del día y 10 kg de fruta madura*) → **Enviar**.
3. Lee el resumen. Escribe **sí** y Enter.

**Debe verse:** resumen con `25 kg de pan dulce`, `10 kg de fruta`, `Total: 35 kg`, `Caduca: … 23:59`, “¿Lo confirmo?”. Luego *“¡Listo! Registré tu
donación #1 (35 kg)”* y un mensaje del **Agente Coordinador**: *“Ofrecí tu donación a Comedor Comunitario Santa Cecilia…”*. A la derecha, el panel *Tu donación*.

**Decir:** "Escribimos como hablaría el encargado, sin formularios. El Captador entiende cantidades y caducidad y pide confirmar. En dos mensajes quedó
registrada y el Coordinador ya la ofreció al receptor que mejor la aprovecha."

### Escena 2 · Cómo decidieron los agentes (Seguimiento)
**Hacer:** pestaña **Seguimiento** (se selecciona la donación). Recorre de arriba abajo: los pasos, el mapa, **“Cómo eligió al receptor”** y la **línea de tiempo**.

**Debe verse:** tabla con los cinco receptores, cada uno con su puntaje y barras de colores (Santa Cecilia ≈ 87 y Banco de Alimentos ≈ 87, casi empatados). En la línea de tiempo: Captador → Orquestador → Coordinador.

**Decir:** "Las decisiones no son una caja negra: el puntaje combina necesidad, cercanía y capacidad, y cada receptor descartado queda con su motivo.
Esta línea de tiempo es la bitácora: se ve qué agente decidió qué y cuándo intervino el orquestador."

### Escena 3 · Rechazo, reasignación, recolección y entrega (Operación)
**Hacer:**
1. Pestaña **Operación** → Receptor **Comedor Comunitario Santa Cecilia** → en la oferta pulsa **Rechazar**.
2. Cambia el receptor a **Banco de Alimentos Nueva Esperanza** (la oferta se reasignó) → **Aceptar**.
3. Sección *Voluntario* → **Mariana López · auto** → **Aceptar recolección** → **Ya recogí con el donante** → **Ya entregué en el receptor**.

**Debe verse:** ruta ≈ 11.7 km, ~28 min. (Si en Seguimiento aparece otro voluntario como propuesta, usa ese.) Avisos verdes tras cada acción.

**Decir:** "El receptor puede rechazar y el Coordinador reasigna al siguiente mejor. Al aceptar, el Logístico elige al voluntario con la ruta más corta que cumpla
capacidad del vehículo, hielera si hace falta frío y horarios. Los voluntarios son simulados en este MVP."

### Escena 4 · Confirmación e impacto
**Hacer:** en *Receptor* (Banco de Alimentos) → “Por confirmar recepción”: cambia los kilos a **24** → **Confirmar recepción**. Pestaña **Impacto**. Pestaña **Donar**: baja al final del chat.

**Debe verse:** Impacto → *24 kg rescatados · 48 raciones · 16 personas (est.) · ≈33 kg de CO2e*, por tipo de alimento y municipio. En el chat: *“¡Rescate completado!…”*.

**Decir:** "El receptor confirma lo que realmente recibió y el Agente de Impacto lo convierte en kilos, raciones, personas beneficiadas y CO2e. Los supuestos están a la vista y
los vamos a validar con un banco de alimentos real. El donante recibe su constancia en el mismo chat."

### Escena 5 · Riesgo y revisión humana; alimento no aceptado
**Hacer:**
1. **Donar** → donante **Hotel Plaza Real (cocina)** → ejemplo **“Pollo y leche (riesgo)”** → Enviar → **sí**.
2. **Operación** → sección *Administrador*: aparece “Alimentos de riesgo por validar” → **Aprobar**.
3. **Seguimiento** → la donación #2: solo receptores con refrigeración son viables.
4. **Donar** → ejemplo **“Alimento no aceptado”** → Enviar.

**Debe verse:** el resumen con “⚠ Incluye alimentos de riesgo…”; la donación en *En revisión humana* hasta que se aprueba; en la tabla, receptores sin refrigeración como *Descartado: sin refrigeración*; y *“No puedo registrar esta donación: ‘cerveza’ no se acepta…”*.

**Decir:** "Con carne o lácteos ninguna decisión sensible se ejecuta sin una persona: la donación espera en la cola de validación y nadie recibe ofertas hasta que se aprueba. Y las reglas de inocuidad bloquean lo que no puede donarse."

### Escena 6 · Cierre honesto
**Decir:** "En resumen: cuatro agentes coordinados por un orquestador, supervisión humana en lo sensible, decisiones explicables y un tablero de impacto, con 68 pruebas automáticas.
Con honestidad: es un MVP con datos simulados; los agentes usan reglas, todavía sin un modelo de lenguaje; no hay autenticación, fotos ni WhatsApp. Lo que sigue es incorporar un LLM al Captador,
validar con un banco de alimentos real y completar los diagramas UML para el 24 de noviembre."

## 5. Si algo sale distinto

| Problema | Qué hacer |
|---|---|
| Ofrecieron a otro receptor | Usa el que muestre **Seguimiento**; los puntajes de Santa Cecilia y el Banco están casi empatados |
| Estado raro o donación a medias | **Operación → Reiniciar datos de demo**, F5 y repite la escena |
| La hora ya no es 16:00 | Detén el servidor y vuelve a ejecutar `.\scripts\demo.ps1` |
| “No pude conectar con la API” | El servidor no corre: ejecuta `.\scripts\demo.ps1` |
| Puerto ocupado | `.\scripts\demo.ps1 -Puerto 8080` |
| El agente no entiende un mensaje | Usa los **ejemplos** de la pestaña Donar, que están probados |

## 6. Qué NO decir

- No digas que usa un LLM o WhatsApp: no es así en esta versión.
- No presentes los factores de CO2e como definitivos ni los datos como reales.
