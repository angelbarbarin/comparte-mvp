# ComParte (MVP)

**Plataforma agéntica de rescate de alimentos** para el Área Metropolitana de Guadalajara. Conecta el excedente de panaderías,
supermercados, mercados y cocinas con bancos de alimentos, comedores y albergues, antes de que caduque. Proyecto del Hackathon de
Desarrollo Sustentable de *Diseño de Software* (ITESO, otoño 2026) · **ODS 2: Hambre cero**.

> **Estado: MVP.** Recorre de punta a punta, con datos de prueba, el ciclo donante → Captador → (revisión humana si hay riesgo) →
> Coordinador → Logístico → Impacto. Lo que hace y lo que **no** hace: [`docs/ALCANCE.md`](docs/ALCANCE.md).
> Importante: en esta versión los agentes usan **reglas, sin modelo de lenguaje (LLM)**.

## Los agentes

| Agente | Qué hace | Código |
|---|---|---|
| **Captador** | Conversa con el donante, estructura la donación y aplica reglas de inocuidad | [`comparte/agentes/captador.py`](comparte/agentes/captador.py) |
| **Coordinador** | Elige al receptor con un puntaje explicable y reasigna si rechaza | [`comparte/agentes/coordinador.py`](comparte/agentes/coordinador.py) |
| **Logístico** | Elige voluntario, calcula la ruta y da seguimiento | [`comparte/agentes/logistico.py`](comparte/agentes/logistico.py) |
| **Impacto** | Calcula kg, raciones, personas y CO2e | [`comparte/agentes/impacto.py`](comparte/agentes/impacto.py) |
| **Orquestador** | Los enruta, pide revisión humana y registra cada decisión | [`comparte/orquestador.py`](comparte/orquestador.py) |

La interfaz muestra el puntaje desglosado, el motivo de cada descarte y una línea de tiempo con cada decisión. El canal es un **chat web**
(plan B ante el costo de WhatsApp Business). Diagramas en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Probarlo

Requisitos: Python 3.11 o superior (probado con 3.13). Funciona sin internet y sin claves (con internet se ven los mosaicos del mapa).

**Windows (PowerShell)**

```powershell
.\scripts\demo.ps1
```

**macOS / Linux**

```bash
./scripts/demo.sh
```

Abre <http://127.0.0.1:8000>. El script crea el entorno virtual, instala dependencias, recarga los datos de prueba, fija la hora de la aplicación
a las 16:00 (así la demo no depende de la hora real) y arranca el servidor. Para grabar el video: [`docs/GUION_VIDEO.md`](docs/GUION_VIDEO.md).

<details>
<summary>Instalación manual</summary>

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m comparte --hora-demo 16:00 --reiniciar
```

Si tu carpeta está en OneDrive, crea el entorno virtual fuera (por ejemplo `%USERPROFILE%\.venvs\comparte`) y define `COMPARTE_VENV` antes del script.
</details>

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest        # 68 pruebas, pocos segundos, sin red ni claves
```

## Estructura

```
comparte/
  agentes/         captador, coordinador, logistico, impacto
  orquestador.py   enruta entre agentes y pide revisión humana
  nlu.py           comprensión de lenguaje por reglas (aquí entraría un LLM)
  conocimiento.py  catálogo de alimentos, inocuidad, factores de impacto, distancias
  api.py           API REST (/api, documentación en /docs)
  modelos.py       Donante, Receptor, Voluntario, Conversacion, Donacion, Evento
  datos.py         piloto simulado del AMG
web/               interfaz (HTML + CSS + JavaScript, sin compilación)
tests/             pruebas
docs/              alcance, arquitectura, guion del video y entrega
scripts/           arranque de la demo
```

## Trabajar en equipo

- `main` siempre debe pasar `pytest`. Una rama por tarea (`feat/<tema>`, `fix/<tema>`) y *pull request* revisado por otra persona.
- Commits: `tipo(área): resumen` y un cuerpo que explique qué y por qué.
- El dominio va en español; la hora siempre con `reloj.ahora()`; toda decisión de un agente deja un evento con `evento(...)`;
  nunca `innerHTML` con datos en la interfaz.
- Recetas: un alimento nuevo → `comparte/conocimiento.py` (sinónimos y factor); cambiar la asignación → `PESOS` en `coordinador.py`;
  un endpoint → `comparte/api.py` + prueba en `tests/test_api.py`.

## Datos y supuestos

Donantes, receptores y voluntarios son **ficticios** (coordenadas aproximadas de colonias reales). Los factores de raciones, personas y CO2e son
supuestos por validar. Las reglas de inocuidad son heurísticas del equipo, **no una certificación sanitaria**.

## Equipo y licencia

Diego Alejandro Álvarez Hernández · Angel Isaac Barbarín Cuevas · Diego Valerio. Código abierto bajo licencia [MIT](LICENSE).
