// Interfaz de ComParte (MVP): JavaScript sin dependencias ni compilación, salvo Leaflet para el mapa.
// Todo texto entra como nodo de texto (nunca innerHTML con datos): un mensaje con HTML no puede inyectar código.
// Cada acción manda el token del usuario de prueba con el que "actúa" la pestaña (cabecera X-Comparte-Token).
'use strict';

// ---------------------------------------------------------------------------------- utilidades
function el(tag, props, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith('on')) nodo.addEventListener(k.slice(2), v);
    else if (k === 'class') nodo.className = v;
    else nodo.setAttribute(k, v === true ? '' : v);
  }
  for (const h of hijos.flat(Infinity)) {
    if (h === null || h === undefined || h === false) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return nodo;
}
function llenar(nodo, ...hijos) { nodo.replaceChildren(); nodo.append(...hijos.flat(Infinity).filter((h) => h !== null && h !== undefined && h !== false).map((h) => (h instanceof Node ? h : document.createTextNode(String(h))))); return nodo; }

// SVG: íconos (trazos propios, 24x24), gráficas y mapa de respaldo. Los atributos son constantes o números.
const NS = 'http://www.w3.org/2000/svg';
function svg(tag, attrs, ...hijos) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, v);
  for (const h of hijos.flat(Infinity)) if (h !== null && h !== undefined && h !== false) n.append(h instanceof Node ? h : document.createTextNode(String(h)));
  return n;
}
const ICONOS = {
  casa: ['M3 11 12 3l9 8', 'M5 10v10h14V10', 'M10 20v-6h4v6'],
  mensaje: ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  pin: ['M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z', { c: [12, 9, 2.5] }],
  portapapeles: ['M9 3h6v4H9z', 'M8 5H5v16h14V5h-3', 'm9 14 2 2 4-4'],
  grafica: ['M4 20V11', 'M10 20V4', 'M16 20v-7', 'M21 20H3'],
  escudo: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z', 'm9 12 2 2 4-4'],
  diana: [{ c: [12, 12, 9] }, { c: [12, 12, 5] }, { c: [12, 12, 1.5] }],
  camion: ['M2 6h12v10H2z', 'M14 10h4l3 3v3h-7', { c: [6.5, 17.5, 2] }, { c: [17.5, 17.5, 2] }],
  hoja: ['M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10Z', 'M2 21c0-3 1.9-5.4 5.1-6 2.4-.5 4.9-2 5.9-3'],
  red: [{ c: [12, 5, 2.2] }, { c: [5, 19, 2.2] }, { c: [19, 19, 2.2] }, 'M12 7.2V12m0 0-5.4 5.4M12 12l5.4 5.4'],
  persona: [{ c: [12, 8, 4] }, 'M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1'],
  grupo: [{ c: [9, 8, 3.5] }, { c: [17.5, 9, 2.5] }, 'M2 20a7 7 0 0 1 14 0', 'M16 14.6A5 5 0 0 1 22 19.5'],
  reloj: [{ c: [12, 12, 9] }, 'M12 7v5l3 2'],
  paquete: ['M21 8 12 3 3 8l9 5 9-5z', 'M3 8v8l9 5 9-5V8', 'M12 13v8'],
  balanza: ['M12 3v18', 'M7 21h10', 'M5 7h14', 'M5 7l-3 7a3 3 0 0 0 6 0z', 'M19 7l-3 7a3 3 0 0 0 6 0z'],
  plato: [{ c: [12, 13, 7] }, { c: [12, 13, 3.5] }, 'M3 4v5m0 0v11M5 4v5H1V4', 'M21 4c-2 1-2 4-2 6h2v10'],
  nube: ['M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 1 1 0 9Z'],
  auto: ['M5 16h14', 'M3 16v-4l2-5h14l2 5v4h-2', { c: [7, 17, 2] }, { c: [17, 17, 2] }],
  check: ['M5 12l5 5L20 7'],
  equis: ['M6 6l12 12M18 6 6 18'],
  alerta: ['M12 3 2 20h20L12 3z', 'M12 10v4', 'M12 17h.01'],
  flecha: ['M5 12h14', 'm13 6 6 6-6 6'],
  enviar: ['M22 2 11 13', 'M22 2l-7 20-4-9-9-4 20-7z'],
  recargar: ['M3 12a9 9 0 0 1 15.5-6.2L21 8', 'M21 3v5h-5', 'M21 12a9 9 0 0 1-15.5 6.2L3 16', 'M3 21v-5h5'],
  corazon: ['M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z'],
  casaAyuda: ['M3 11 12 3l9 8', 'M5 10v10h14V10', 'M12 18s-3-1.8-3-3.6a1.6 1.6 0 0 1 3-.8 1.6 1.6 0 0 1 3 .8c0 1.8-3 3.6-3 3.6z'],
  copo: ['M12 2v20', 'M4.9 7l14.2 10', 'M4.9 17 19.1 7', 'm9 4 3 3 3-3', 'm9 20 3-3 3 3'],
};
function icono(nombre, clase = '') {
  return svg('svg', { viewBox: '0 0 24 24', class: `icono ${clase}`.trim(), 'aria-hidden': 'true' },
    (ICONOS[nombre] || []).map((p) => (typeof p === 'string' ? svg('path', { d: p }) : svg('circle', { cx: p.c[0], cy: p.c[1], r: p.c[2] }))));
}

// Tokens de prueba (solo valen con el servidor en modo demo: python -m comparte --demo).
const TOKEN = {
  admin: 'demo-admin',
  donante: (id) => `demo-donante-${id}`,
  receptor: (id) => `demo-receptor-${id}`,
  voluntario: (id) => `demo-voluntario-${id}`,
};
const sinPunto = (t) => String(t).replace(/[.\s]+$/, '');
function mensajeDeError(estado, detalle) {
  if (estado === 401) return 'No reconocí al usuario de prueba de esta pestaña. Recarga la página; si sigue igual, arranca el servidor con --demo.';
  if (estado === 403) { const d = sinPunto(detalle || 'le toca a otro usuario'); return `Esa acción no te corresponde: ${d.charAt(0).toLowerCase()}${d.slice(1)}.`; }
  if (estado === 409) return `${sinPunto(detalle || 'Esta oferta ya fue respondida o venció')}. Ya actualicé la vista.`;
  return detalle || 'Los datos enviados no son válidos';
}
async function api(metodo, ruta, cuerpo, token) {
  const headers = {};
  if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['X-Comparte-Token'] = token;
  const r = await fetch('/api' + ruta, { method: metodo, headers, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (!r.ok) {
    const error = new Error(mensajeDeError(r.status, datos && typeof datos.detail === 'string' ? datos.detail : null));
    error.estado = r.status;
    throw error;
  }
  return datos;
}
const GET = (ruta, token) => api('GET', ruta, undefined, token);
const POST = (ruta, cuerpo = {}, token) => api('POST', ruta, cuerpo, token);

// Evita el doble clic: mientras una petición está en curso se desactivan los botones de su tarjeta (o formulario)
// y no se repite la misma ruta. El servidor también lo impide (409), pero así ni siquiera se envía.
const enVuelo = new Set();
async function sinDobleClic(ev, clave, trabajo) {
  if (enVuelo.has(clave)) return undefined;
  const origen = ev && ev.currentTarget instanceof Element ? ev.currentTarget : null;  // se lee antes del primer await
  const zona = origen ? origen.closest('.tarea, form, .fila') || origen : null;
  const botones = zona ? [...zona.querySelectorAll('button')].concat(zona.matches('button') ? [zona] : []) : [];
  enVuelo.add(clave);
  for (const b of botones) { b.disabled = true; }
  if (origen && origen.matches('button')) origen.setAttribute('aria-busy', 'true');
  try { return await trabajo(); } finally {
    enVuelo.delete(clave);
    for (const b of botones) { b.disabled = false; b.removeAttribute('aria-busy'); }
  }
}

function aviso(texto, tipo = '') {
  const n = el('div', { class: tipo }, tipo ? icono(tipo === 'error' ? 'alerta' : 'check') : null, el('span', null, texto));
  document.getElementById('avisos').append(n);
  setTimeout(() => n.remove(), tipo === 'error' ? 7000 : 4000);
}
const prefs = {
  leer(k, d) { try { const v = localStorage.getItem('comparte.' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  guardar(k, v) { try { localStorage.setItem('comparte.' + k, JSON.stringify(v)); } catch (e) { /* modo privado */ } },
};
const firmas = new Map(); // repinta solo si los datos cambian, para no borrar lo que se está escribiendo
function pintar(clave, datos, fn) {
  const f = JSON.stringify(datos);
  if (firmas.get(clave) === f) return;
  firmas.set(clave, f);
  fn(datos);
}
const kg = (n) => `${Number(n).toLocaleString('es-MX', { maximumFractionDigits: 1 })} kg`;
const num = (n) => Number(n).toLocaleString('es-MX', { maximumFractionDigits: 0 });
const textoItems = (items) => items.map((i) => `${i.cantidad} ${i.unidad} ${i.nombre}`).join(', ');
const fecha = (iso) => new Date(iso).toLocaleString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
const hora = (iso) => new Date(iso).toLocaleTimeString('es-MX', { hour: 'numeric', minute: '2-digit' });
const sinMovimiento = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Contador animado: sube del valor anterior al nuevo (solo cuando cambia el dato).
function contar(nodo, valor, formato = num) {
  const desde = Number(nodo.dataset.valor || 0);
  nodo.dataset.valor = valor;
  if (sinMovimiento() || desde === valor) { nodo.textContent = formato(valor); return; }
  const inicio = performance.now(), dur = 1100;
  const paso = (t) => {
    const p = Math.min(1, (t - inicio) / dur), e = 1 - (1 - p) ** 3;
    nodo.textContent = formato(desde + (valor - desde) * e);
    if (p < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
}

const AGENTES = {
  captador: ['Agente Captador', 'escudo'], coordinador: ['Agente Coordinador', 'diana'], logistico: ['Agente Logístico', 'camion'],
  impacto: ['Agente de Impacto', 'hoja'], orquestador: ['Orquestador', 'red'], humano: ['Persona', 'persona'], donante: ['Donante', 'persona'],
};
const agente = (a) => (AGENTES[a] ? a : 'orquestador');
const avatar = (a, tam = '') => el('span', { class: `avatar ${tam}`.trim(), style: `--c:var(--${agente(a)})`, title: AGENTES[agente(a)][0] }, icono(AGENTES[agente(a)][1]));
const insignia = (a) => el('span', { class: 'insignia', style: `--c:var(--${agente(a)})` }, AGENTES[agente(a)][0]);
const ESTADOS = {
  registrada: ['Registrada', 'info'], pendiente_validacion: ['En revisión humana', 'alerta'], rechazada: ['Rechazada', 'error'],
  ofrecida: ['Ofrecida a un receptor', 'info'], sin_receptor: ['Sin receptor', 'error'], asignada: ['Receptor aceptó', 'info'],
  sin_voluntario: ['Sin voluntario', 'error'], en_recoleccion: ['Voluntario va por ella', 'info'], en_camino: ['En camino al receptor', 'info'],
  entregada: ['Entregada · falta confirmar', 'alerta'], completada: ['Completada', 'ok'],
};
const chipEstado = (e) => el('span', { class: `chip ${(ESTADOS[e] || [])[1] || ''}` }, (ESTADOS[e] || [e])[0]);

// Progreso de la donación: una bolita con ícono por etapa, unidas por una línea que se ilumina.
function etapas(d) {
  const lista = [['Registrada', 'mensaje'], ...(d.requiere_revision ? [['Revisión', 'persona']] : []), ['Receptor', 'casaAyuda'],
    ['Voluntario', 'camion'], ['Recolección', 'paquete'], ['Entrega', 'pin'], ['Completada', 'check']];
  const i = (n) => lista.findIndex(([x]) => x === n);
  const activo = { registrada: 0, pendiente_validacion: i('Revisión'), rechazada: i('Revisión'), ofrecida: i('Receptor'), sin_receptor: i('Receptor'),
    asignada: i('Voluntario'), sin_voluntario: i('Voluntario'), en_recoleccion: i('Recolección'), en_camino: i('Entrega'), entregada: i('Completada'), completada: lista.length }[d.estado] ?? 0;
  const fallo = ['sin_receptor', 'sin_voluntario', 'rechazada'].includes(d.estado);
  return el('ol', { class: 'etapas', 'aria-label': 'Progreso de la donación' },
    lista.map(([n, ic], k) => {
      const estado = k < activo ? 'hecho' : k === activo ? (fallo ? 'fallo' : 'activo') : '';
      return el('li', { class: estado, 'aria-current': k === activo ? 'step' : null },
        el('span', { class: 'bola' }, icono(k < activo ? 'check' : estado === 'fallo' ? 'equis' : ic)), el('span', null, n));
    }));
}

const ctx = { donantes: [], receptores: [], voluntarios: [], pesos: {}, modoDemo: true };
let donaciones = [];

// ------------------------------------------------------------------------------------------ Inicio
const Inicio = (() => {
  const seccion = document.getElementById('vista-inicio');
  const cifra = (ic, color, unidad, que) => {
    const valor = el('span', null, '0');
    return { valor, nodo: el('div', { class: 'cifra-grande' }, el('span', { class: 'avatar', style: `--c:${color}` }, icono(ic)),
      el('div', null, el('b', null, valor, unidad ? el('small', null, unidad) : null), el('span', { class: 'que' }, que))) };
  };
  const kgC = cifra('paquete', 'var(--neon)', 'kg', 'de comida rescatada');
  const racC = cifra('plato', 'var(--amarillo)', '', 'raciones que llegaron a un plato');
  const co2C = cifra('nube', 'var(--neon-2)', 'kg', 'de CO2e que no se emitieron');
  const enCurso = el('span', { class: 'chip info' }, '0 en curso');

  const PASOS = [
    ['captador', 'Captador', 'Conversa con el negocio en español, entiende qué sobró y cuánto, y revisa que sea seguro donarlo.'],
    ['coordinador', 'Coordinador', 'Elige al comedor o albergue que más lo necesita y alcanza a recibirlo antes de que caduque.'],
    ['logistico', 'Logístico', 'Busca al voluntario más cercano con el vehículo adecuado y le traza la ruta.'],
    ['impacto', 'Impacto', 'Al confirmar la entrega, mide kg, raciones, personas alimentadas y CO2e evitado.'],
  ];
  const ROLES = [
    ['donante', 'Soy un negocio', 'Panaderías, fruterías y restaurantes registran su excedente con un chat.', '#donar', 'Donar ahora'],
    ['coordinador', 'Soy un comedor', 'Recibe ofertas que encajan con lo que necesitas y confirma lo que llegó.', '#operacion', 'Ver ofertas'],
    ['logistico', 'Soy voluntario', 'Acepta recolecciones cerca de ti con la ruta ya calculada.', '#operacion', 'Ver recolecciones'],
    ['impacto', 'Quiero ver el impacto', 'Kilos, raciones y CO2e de cada rescate, medidos por un agente.', '#impacto', 'Ver tablero'],
  ];
  seccion.append(
    el('div', { class: 'heroe' },
      el('div', null,
        el('span', { class: 'ceja' }, icono('hoja'), 'ODS 2 · Hambre cero'),
        el('h1', null, 'La comida que sobra hoy puede ser la ', el('span', { class: 'neon' }, 'cena de alguien'), ' esta noche.'),
        el('p', { class: 'lead' }, 'ComParte conecta los excedentes de negocios de Guadalajara con comedores y albergues. Cuatro agentes inteligentes hacen el trabajo pesado: entender la donación, elegir a quién darla, organizar la recolección y medir el impacto.'),
        el('div', { class: 'acciones' },
          el('a', { class: 'boton primario grande', href: '#donar' }, icono('mensaje'), 'Donar ahora'),
          el('a', { class: 'boton fantasma grande', href: '#impacto' }, 'Ver el impacto', icono('flecha')))),
      el('div', { class: 'tarjeta vivo' },
        el('div', { class: 'encabezado' }, el('span', { class: 'en-vivo' }, 'En vivo en esta demo'), enCurso),
        kgC.nodo, racC.nodo, co2C.nodo)),
    el('section', { class: 'seccion-inicio', 'aria-labelledby': 'h-problema' },
      el('header', null, el('span', { class: 'ceja' }, icono('alerta'), 'El problema'), el('h2', { id: 'h-problema' }, 'En México sobra comida y aun así falta en muchas mesas')),
      el('div', { class: 'problema' },
        el('div', { class: 'tarjeta dato-problema' }, el('b', null, '20.4', el('small', null, ' millones de t')),
          el('p', null, 'de alimentos se pierden o desperdician cada año: el 34 % de lo que se produce para consumo humano.'), el('cite', null, 'Banco Mundial, Pérdidas y desperdicios de alimentos en México')),
        el('div', { class: 'tarjeta dato-problema' }, el('b', null, '14.4', el('small', null, ' %')),
          el('p', null, 'de la población tiene carencia por acceso a una alimentación nutritiva y de calidad.'), el('cite', null, 'INEGI, Pobreza multidimensional 2024')),
        el('div', { class: 'tarjeta dato-problema' }, el('b', null, '36', el('small', null, ' millones de t')),
          el('p', null, 'de CO2 equivalente genera ese desperdicio. Rescatar comida también es acción climática.'), el('cite', null, 'Banco Mundial')))),
    el('section', { class: 'seccion-inicio', 'aria-labelledby': 'h-flujo' },
      el('header', null, el('span', { class: 'ceja' }, icono('red'), 'Cómo funciona'), el('h2', { id: 'h-flujo' }, 'Cuatro agentes, un rescate de punta a punta')),
      el('div', { class: 'flujo' }, PASOS.map(([a, t, x]) => el('div', { class: 'tarjeta paso-agente', style: `--c:var(--${a})` }, avatar(a, 'grande'), el('h3', null, t), el('p', null, x)))),
      el('p', { class: 'nota-flujo' }, avatar('orquestador', 'chico'),
        el('span', null, 'Un orquestador decide qué agente actúa en cada momento. Los alimentos de riesgo (carne, lácteos, comida preparada) siempre pasan por una persona antes de asignarse.'))),
    el('section', { class: 'seccion-inicio', 'aria-labelledby': 'h-roles' },
      el('header', null, el('span', { class: 'ceja' }, icono('corazon'), 'Pruébalo'), el('h2', { id: 'h-roles' }, '¿Desde dónde quieres verlo?')),
      el('div', { class: 'roles' }, ROLES.map(([a, t, x, href, ir]) => el('a', { class: 'tarjeta rol', href },
        avatar(a), el('h3', null, t), el('p', null, x), el('span', { class: 'ir' }, ir, icono('flecha')))))));

  return {
    async activar() { firmas.delete('inicio'); await this.refrescar(); },
    async refrescar() {
      const [r] = await Promise.all([GET('/impacto'), cargarDonaciones()]);
      const activas = donaciones.filter((d) => !['completada', 'rechazada'].includes(d.estado)).length;
      pintar('inicio', [r.totales, activas], () => {
        contar(kgC.valor, r.totales.kg); contar(racC.valor, r.totales.raciones); contar(co2C.valor, r.totales.co2e_kg);
        enCurso.textContent = `${activas} ${activas === 1 ? 'donación' : 'donaciones'} en curso`;
      });
    },
  };
})();

// ------------------------------------------------------------------------------------------ Donar
const Donar = (() => {
  const seccion = document.getElementById('vista-donar');
  let donanteId = prefs.leer('donanteId', null);
  const selector = el('select', { id: 'donante', onchange: () => { donanteId = Number(selector.value); prefs.guardar('donanteId', donanteId); firmas.delete('chat'); Donar.refrescar(); } });
  const mensajes = el('div', { class: 'mensajes', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversación con el Agente Captador' });
  const entrada = el('input', { type: 'text', id: 'texto', placeholder: 'Escribe qué te sobró, cuánto y hasta cuándo…', autocomplete: 'off', maxlength: 2000, 'aria-label': 'Mensaje' });
  const panel = el('div');
  const EJEMPLOS = [
    ['Pan del día y fruta', 'Tengo 25 kg de pan dulce del día y 10 kg de fruta madura'],
    ['Pollo y leche (riesgo)', 'Tengo 12 kg de pollo y 8 litros de leche, vence mañana'],
    ['Falta la cantidad', 'Tengo pan dulce'],
    ['Alimento no aceptado', 'Tengo 10 litros de cerveza'],
  ];
  const escribiendo = el('div', { class: 'msj escribiendo', style: '--c:var(--captador)', 'aria-label': 'El Captador está escribiendo' }, avatar('captador', 'chico'), el('div', { class: 'globo' }, el('i'), el('i'), el('i')));
  seccion.append(el('div', { class: 'rejilla chat-y-panel' },
    el('div', { class: 'tarjeta chat-tarjeta' },
      el('div', { class: 'chat-cabeza' }, avatar('captador'), el('div', { class: 'quien' }, el('b', null, 'Agente Captador'), el('span', null, 'En línea · confirma antes de registrar'))),
      el('div', { class: 'chat-barra' },
        el('div', { class: 'campo' }, el('label', { for: 'donante' }, 'Actuar como donante'), selector),
        el('button', { class: 'boton fantasma', type: 'button', onclick: nueva }, icono('recargar'), 'Nueva conversación')),
      mensajes,
      el('form', { class: 'redactor', onsubmit: enviar }, entrada, el('button', { class: 'boton primario', type: 'submit', 'aria-label': 'Enviar' }, icono('enviar'))),
      el('div', { class: 'ejemplos' }, el('span', { class: 'sub' }, 'Prueba con:'),
        EJEMPLOS.map(([t, x]) => el('button', { class: 'chip', type: 'button', onclick: () => { entrada.value = x; entrada.focus(); } }, t)))),
    el('div', null,
      el('div', { class: 'tarjeta donacion-actual' }, el('h2', null, 'Tu donación'), panel),
      el('div', { class: 'tarjeta' }, el('h3', null, 'Quién hace qué'),
        el('ul', { class: 'agentes-lista' },
          [['captador', 'entiende tu mensaje y revisa la inocuidad.'], ['coordinador', 'elige al receptor que más lo necesita y llega a tiempo.'],
            ['logistico', 'busca voluntario y calcula la ruta.'], ['impacto', 'mide kg, raciones, personas y CO2e.'],
            ['orquestador', 'los coordina y pide revisión humana si hay riesgo.']]
            .map(([a, t]) => el('li', { style: `--c:var(--${a})` }, avatar(a, 'chico'), el('div', null, el('b', null, AGENTES[a][0]), t))))))));

  async function enviar(ev) {
    ev.preventDefault();
    const texto = entrada.value.trim();
    if (!texto) return;
    await sinDobleClic({ currentTarget: ev.currentTarget }, `chat-${donanteId}`, async () => {
      entrada.readOnly = true;
      mensajes.append(el('div', { class: 'msj mio' }, el('div', { class: 'globo' }, texto)), escribiendo);
      mensajes.scrollTop = mensajes.scrollHeight;
      entrada.value = '';
      try {
        const [r] = await Promise.all([POST(`/chat/${donanteId}`, { texto }, TOKEN.donante(donanteId)), new Promise((ok) => setTimeout(ok, sinMovimiento() ? 0 : 450))]);
        firmas.delete('chat');
        pintarChat(r.mensajes);
        if (r.donacion_id) aviso(`Donación #${r.donacion_id} registrada. Sigue su avance en “Seguimiento”.`, 'ok');
        await cargarDonaciones();
        pintarPanel();
      } catch (e) {
        escribiendo.remove(); entrada.value = texto; aviso(e.message, 'error');
      } finally { entrada.readOnly = false; entrada.focus(); }
    });
  }
  async function nueva(ev) {
    await sinDobleClic(ev, `chat-${donanteId}`, async () => {
      try { pintarChat((await POST(`/chat/${donanteId}/nueva`, {}, TOKEN.donante(donanteId))).mensajes); } catch (e) { aviso(e.message, 'error'); }
    });
  }
  function pintarChat(lista) {
    pintar('chat', lista, (ms) => {
      llenar(mensajes, ms.map((m) => (m.rol === 'donante'
        ? el('div', { class: 'msj mio' }, el('div', { class: 'globo' }, m.texto))
        : el('div', { class: 'msj', style: `--c:var(--${agente(m.rol)})` }, avatar(m.rol, 'chico'),
          el('div', { class: 'globo' }, el('span', { class: 'nombre' }, AGENTES[agente(m.rol)][0]), m.texto)))));
      mensajes.scrollTop = mensajes.scrollHeight;
    });
  }
  function pintarPanel() {
    const d = donaciones.find((x) => x.donante.id === donanteId);
    pintar('panel', d || null, () => llenar(panel, d ? [
      el('div', { class: 'fila entre', style: 'margin-top:.4rem' }, el('span', { class: 'sub' }, `Donación #${d.id}`), chipEstado(d.estado)),
      el('div', { class: 'peso' }, num(d.total_kg), el('small', null, ' kg')),
      el('p', { class: 'sub' }, textoItems(d.items)),
      etapas(d),
      d.receptor ? el('p', { style: 'margin-top:.6rem' }, el('span', { class: 'sub' }, 'Receptor: '), el('b', null, d.receptor.nombre)) : null,
      el('a', { class: 'boton', style: 'margin-top:.8rem', href: `#seguimiento/${d.id}` }, 'Ver seguimiento completo', icono('flecha')),
    ] : el('p', { class: 'vacio' }, 'Cuando confirmes tu donación verás aquí su avance, etapa por etapa.')));
  }
  return {
    async activar() {
      llenar(selector, ctx.donantes.map((d) => el('option', { value: d.id }, `${d.nombre} · ${d.municipio}`)));
      if (!ctx.donantes.some((d) => d.id === donanteId)) donanteId = ctx.donantes[0].id;
      selector.value = donanteId;
      firmas.clear();
      await this.refrescar();
    },
    async refrescar() {
      if (enVuelo.has(`chat-${donanteId}`)) return;  // no borra el "escribiendo…" a media respuesta
      await cargarDonaciones(); pintarChat((await GET(`/chat/${donanteId}`, TOKEN.donante(donanteId))).mensajes); pintarPanel();
    },
  };
})();

// ------------------------------------------------------------------------------------- Seguimiento
const Seguimiento = (() => {
  const seccion = document.getElementById('vista-seguimiento');
  let sel = null, mapa = null, capa = null, firmaMapa = null;
  const lista = el('ul', { class: 'lista' });
  const detalle = el('div');
  const mapaDiv = el('div', { id: 'mapa', role: 'img', 'aria-label': 'Mapa con donante, receptor y voluntario' });
  seccion.append(el('div', { class: 'rejilla doc' }, el('div', { class: 'tarjeta' }, el('h2', null, 'Donaciones'), el('p', { class: 'sub' }, 'Elige una para ver cada decisión de los agentes.'), lista), detalle));
  const COMP = [['necesidad', 'Necesidad', 'var(--captador)'], ['cercania', 'Cercanía', 'var(--coordinador)'], ['capacidad', 'Capacidad', 'var(--neon)']];
  const COLORES = { donante: '#ffd166', receptor: '#3ddc84', voluntario: '#5ab0ff' };

  const dato = (ic, n, v) => el('div', { class: 'dato' }, icono(ic), el('div', null, el('div', null, n), el('b', null, v)));
  const d_pesos = (k) => ctx.pesos[k] || 0;
  function tablaReceptores(d) {
    if (!d.evaluacion || !d.evaluacion.length) return el('p', { class: 'vacio' }, 'Aún no se evalúan receptores (la donación espera revisión).');
    return el('div', null, el('div', { class: 'envoltura' }, el('table', null,
      el('thead', null, el('tr', null, el('th', null, 'Receptor'), el('th', null, 'Puntaje'), el('th', null, 'Resultado'))),
      el('tbody', null, d.evaluacion.map((c) => el('tr', { class: c.viable ? '' : 'descartado' },
        el('td', null, el('b', null, c.nombre), el('div', { class: 'sub' }, `${c.distancia_km} km · llegaría ${c.llegada}`)),
        el('td', null, c.viable ? [el('b', null, c.puntaje.toFixed(0)), el('span', { class: 'sub' }, ' / 100'),
          el('div', { class: 'barra' }, COMP.map(([k, n, col]) => el('i', { title: `${n}: ${Math.round(100 * c.componentes[k])} %`, style: `width:${100 * d_pesos(k) * c.componentes[k]}%;background:${col}` })))] : `${c.puntaje.toFixed(0)} (ref.)`),
        el('td', null, c.viable ? el('span', { class: 'chip ok' }, 'Viable') : [el('span', { class: 'chip error' }, 'Descartado'), el('ul', { class: 'sub', style: 'margin:.35rem 0 0;padding-left:1rem' }, c.motivos.map((m) => el('li', null, m)))])))))),
      el('div', { class: 'leyenda' }, COMP.map(([k, n, col]) => el('span', { style: `--c:${col}` }, `${n} (${Math.round(100 * d_pesos(k))} %)`))));
  }

  // Sin internet no carga Leaflet: se dibuja un esquema con las posiciones reales (proyección simple de lat/lon).
  function esquema(d) {
    const pts = [['donante', d.donante], d.receptor && ['receptor', d.receptor], d.voluntario && ['voluntario', d.voluntario]].filter(Boolean);
    const W = 800, H = 320, M = 70;
    const lats = pts.map(([, a]) => a.lat), lons = pts.map(([, a]) => a.lon);
    const [la0, la1, lo0, lo1] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
    const esc = Math.min((W - 2 * M) / Math.max(lo1 - lo0, 1e-3), (H - 2 * M) / Math.max(la1 - la0, 1e-3));
    const cx = (W - (lo1 - lo0) * esc) / 2, cy = (H - (la1 - la0) * esc) / 2;
    const xy = (a) => [cx + (a.lon - lo0) * esc, H - (cy + (a.lat - la0) * esc)];
    const p = Object.fromEntries(pts.map(([r, a]) => [r, xy(a)]));
    const linea = (a, b, color, guion) => (p[a] && p[b] ? svg('line', { x1: p[a][0], y1: p[a][1], x2: p[b][0], y2: p[b][1], stroke: color, 'stroke-width': 3, 'stroke-dasharray': guion, 'stroke-linecap': 'round', opacity: .85 }) : null);
    const reja = [];
    for (let x = 0; x <= W; x += 40) reja.push(svg('line', { x1: x, y1: 0, x2: x, y2: H, stroke: '#1a2823' }));
    for (let y = 0; y <= H; y += 40) reja.push(svg('line', { x1: 0, y1: y, x2: W, y2: y, stroke: '#1a2823' }));
    return el('div', { class: 'mapa-esquema', role: 'img', 'aria-label': 'Esquema de ubicaciones (sin conexión al mapa)' },
      svg('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' }, reja,
        linea('voluntario', 'donante', COLORES.voluntario, '8 8'), linea('donante', 'receptor', COLORES.receptor, null),
        pts.map(([r, a]) => svg('g', null,
          svg('circle', { cx: p[r][0], cy: p[r][1], r: 18, fill: COLORES[r], opacity: .18 }),
          svg('circle', { cx: p[r][0], cy: p[r][1], r: 8, fill: COLORES[r], stroke: '#0b1210', 'stroke-width': 3 }),
          svg('text', { x: p[r][0], y: p[r][1] - 24, fill: '#e7f1ec', 'font-size': 14, 'font-weight': 700, 'text-anchor': 'middle', stroke: '#0b1210', 'stroke-width': 5, 'paint-order': 'stroke', 'stroke-linejoin': 'round' }, a.nombre))),
        svg('text', { x: 16, y: H - 14, fill: '#66796f', 'font-size': 12 }, 'Esquema sin conexión · posiciones reales, distancias en línea recta x 1.3')));
  }
  function pintarMapa(d) {
    if (!window.L) return;
    if (!mapa) {
      mapa = L.map(mapaDiv, { scrollWheelZoom: false }).setView([20.67, -103.35], 11);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap' }).addTo(mapa);
      capa = L.layerGroup().addTo(mapa);
    }
    const firma = JSON.stringify([d.id, d.estado, d.receptor && d.receptor.id, d.voluntario && d.voluntario.id]);
    if (firma === firmaMapa) return;
    const otra = !firmaMapa || JSON.parse(firmaMapa)[0] !== d.id;
    firmaMapa = firma;
    capa.clearLayers();
    const pts = [];
    const marca = (rol, a, etiqueta) => { const p = [a.lat, a.lon]; pts.push(p); L.circleMarker(p, { radius: 9, color: '#0b1210', weight: 3, fillColor: COLORES[rol], fillOpacity: 1 }).bindTooltip(`${etiqueta}: ${a.nombre}`).addTo(capa); return p; };
    const pd = marca('donante', d.donante, 'Donante');
    const pr = d.receptor ? marca('receptor', d.receptor, 'Receptor') : null;
    if (d.voluntario) { const pv = marca('voluntario', d.voluntario, 'Voluntario'); L.polyline([pv, pd], { color: COLORES.voluntario, weight: 3, dashArray: '6 6' }).addTo(capa); }
    if (pr) L.polyline([pd, pr], { color: COLORES.receptor, weight: 4 }).addTo(capa);
    if (otra) mapa.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 14 });
  }

  function pintarDetalle(d) {
    llenar(detalle,
      el('div', { class: 'tarjeta' },
        el('div', { class: 'fila entre' }, el('div', null, el('span', { class: 'sub' }, `Donación #${d.id}`), el('h2', null, d.donante.nombre)), chipEstado(d.estado)),
        etapas(d),
        el('div', { class: 'datos' }, dato('paquete', 'Alimentos', textoItems(d.items)), dato('balanza', 'Peso total', kg(d.total_kg)),
          dato('reloj', 'Caduca', fecha(d.caduca_en)), dato('casaAyuda', 'Receptor', d.receptor ? d.receptor.nombre : '—'),
          dato('camion', 'Voluntario', d.voluntario ? `${d.voluntario.nombre} (${d.voluntario.vehiculo})` : '—'),
          dato('pin', 'Ruta', d.ruta && d.ruta.km ? `${d.ruta.km} km · ~${d.ruta.minutos} min` : '—'))),
      el('div', { class: 'tarjeta' }, el('div', { class: 'titulo-tarjeta' }, icono('pin'), el('h3', null, 'Mapa y ruta')),
        window.L ? mapaDiv : esquema(d),
        el('div', { class: 'mapa-leyenda' }, el('span', { style: `--c:${COLORES.donante}` }, 'Donante'), el('span', { style: `--c:${COLORES.receptor}` }, 'Receptor'),
          el('span', { style: `--c:${COLORES.voluntario}` }, 'Voluntario'), el('span', { class: 'sub', style: 'margin-left:auto' }, 'Distancias estimadas: línea recta x 1.3'))),
      el('div', { class: 'tarjeta' }, el('div', { class: 'titulo-tarjeta' }, avatar('coordinador', 'chico'), el('h3', null, 'Cómo eligió al receptor')),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .6rem' }, 'Puntaje 0-100 = necesidad + cercanía + capacidad. Cada descarte conserva su motivo.'), tablaReceptores(d)),
      el('div', { class: 'tarjeta' }, el('div', { class: 'titulo-tarjeta' }, avatar('orquestador', 'chico'), el('h3', null, 'Bitácora de los agentes')),
        el('p', { class: 'sub' }, 'Cada decisión y cada traspaso del orquestador queda registrado.'),
        d.eventos.length ? el('ol', { class: 'bitacora' }, d.eventos.map((e) => el('li', { style: `--c:var(--${agente(e.agente)})` },
          el('div', { class: 'cuando' }, el('time', null, e.hora), insignia(e.agente)), el('p', null, e.resumen)))) : el('p', { class: 'vacio' }, 'Sin eventos.')));
    pintarMapa(d);
    setTimeout(() => mapa && mapa.invalidateSize(), 60);
  }

  return {
    async activar(param) { if (param) sel = Number(param); firmas.clear(); await this.refrescar(); },
    async refrescar() {
      await cargarDonaciones();
      if (!sel && donaciones.length) sel = donaciones[0].id;
      pintar('lista', [donaciones.map((d) => [d.id, d.estado]), sel], () => {
        llenar(lista, donaciones.length ? donaciones.map((d) => el('li', null, el('button', { type: 'button', 'aria-pressed': String(d.id === sel), onclick: () => { location.hash = `#seguimiento/${d.id}`; } },
          el('div', { class: 'fila entre' }, el('b', null, `#${d.id} · ${d.donante.nombre}`)), el('span', { class: 'sub' }, `${textoItems(d.items)} · ${kg(d.total_kg)}`), chipEstado(d.estado))))
          : el('li', { class: 'vacio' }, 'Aún no hay donaciones. Registra una en “Donar”.'));
      });
      if (!sel) { pintar('detalle', null, () => llenar(detalle, el('div', { class: 'tarjeta' }, el('p', { class: 'vacio' }, 'Elige una donación para ver las decisiones de los agentes.')))); return; }
      try { const d = await GET(`/donaciones/${sel}`); pintar('detalle', d, () => pintarDetalle(d)); } catch (e) { sel = null; }
    },
  };
})();

// --------------------------------------------------------------------------------------- Operación
const Operacion = (() => {
  const seccion = document.getElementById('vista-operacion');
  let recId = prefs.leer('receptorId', null), volId = prefs.leer('voluntarioId', null);
  const selRec = el('select', { 'aria-label': 'Receptor', onchange: () => { recId = Number(selRec.value); prefs.guardar('receptorId', recId); firmas.clear(); Operacion.refrescar(); } });
  const selVol = el('select', { 'aria-label': 'Voluntario', onchange: () => { volId = Number(selVol.value); prefs.guardar('voluntarioId', volId); firmas.clear(); Operacion.refrescar(); } });
  const cRec = el('div'), cVol = el('div'), cAdm = el('div');
  const cabeza = (a, t, x) => el('div', { class: 'rol-cabeza' }, avatar(a), el('div', null, el('h2', null, t), el('p', null, x)));
  seccion.append(el('div', { class: 'rejilla' },
    el('div', null,
      el('div', { class: 'tarjeta' }, cabeza('coordinador', 'Receptor', 'Comedores, albergues y bancos de alimentos'), el('label', null, 'Actuar como'), selRec, cRec),
      el('div', { class: 'tarjeta' }, cabeza('logistico', 'Voluntario', 'Recoge con el donante y entrega en el receptor'), el('label', null, 'Actuar como'), selVol, cVol)),
    el('div', { class: 'tarjeta' }, cabeza('humano', 'Administrador', 'Supervisión humana de los alimentos de riesgo'), cAdm)));

  // token: el usuario con el que actúa cada tarjeta (receptor o voluntario elegido, o el administrador).
  function accion(ruta, cuerpo, ok, token) {
    return (ev) => sinDobleClic(ev, ruta, async () => {
      try { await POST(ruta, cuerpo, token); aviso(ok, 'ok'); } catch (e) { aviso(e.message, 'error'); }
      firmas.clear();
      await Operacion.refrescar();
    });
  }
  const boton = (t, fn, clase = '', ic = null) => el('button', { class: `boton ${clase}`, type: 'button', onclick: fn }, ic ? icono(ic) : null, t);
  const subtitulo = (t, n) => el('h3', { class: 'subtitulo' }, t, n === undefined ? null : el('span', { class: 'cuenta' }, n));
  const tarea = (titulo, d, ...extra) => el('div', { class: `tarea ${['ofrecida', 'asignada'].includes(d.estado) ? 'urgente' : ''}` },
    el('div', { class: 'fila entre' }, el('b', null, titulo), chipEstado(d.estado)),
    el('p', null, el('b', null, textoItems(d.items)), el('span', { class: 'sub' }, ` · ${kg(d.total_kg)} de ${d.donante.nombre}`)), ...extra);
  const vence = (iso, que) => (iso ? el('p', { class: 'sub' }, icono('reloj'), ` ${que} vence a las ${hora(iso)}`) : null);

  function pintarReceptor() {
    const mias = donaciones.filter((d) => d.receptor && d.receptor.id === recId);
    const ofertas = mias.filter((d) => d.estado === 'ofrecida'), porConfirmar = mias.filter((d) => d.estado === 'entregada');
    const caminoHacia = mias.filter((d) => ['asignada', 'en_recoleccion', 'en_camino'].includes(d.estado));
    llenar(cRec,
      subtitulo('Ofertas por responder', ofertas.length),
      ofertas.length ? ofertas.map((d) => tarea(`Oferta · donación #${d.id}`, d, el('p', { class: 'sub' }, `Caduca ${fecha(d.caduca_en)}`), vence(d.oferta_vence_en, 'La oferta'),
        el('div', { class: 'fila' }, boton('Aceptar', accion(`/donaciones/${d.id}/receptor`, { aceptar: true }, 'Aceptaste la donación. El Logístico buscará quién la recoja.', TOKEN.receptor(recId)), 'primario', 'check'),
          boton('Rechazar', accion(`/donaciones/${d.id}/receptor`, { aceptar: false }, 'Rechazaste la oferta; el Coordinador buscará otro receptor.', TOKEN.receptor(recId)), 'peligro')))) : el('p', { class: 'vacio' }, 'Sin ofertas por ahora.'),
      subtitulo('Por confirmar recepción', porConfirmar.length),
      porConfirmar.length ? porConfirmar.map((d) => { const entrada = el('input', { type: 'number', min: '0.1', step: '0.1', value: d.total_kg, 'aria-label': 'Kilos realmente recibidos' });
        return tarea(`Donación #${d.id} entregada`, d, el('div', { class: 'fila' }, el('div', { class: 'campo' }, el('label', null, 'Kilos que recibiste (corrígelos si difieren)'), entrada),
          boton('Confirmar recepción', (ev) => accion(`/donaciones/${d.id}/confirmacion`, { kg_recibidos: Number(entrada.value) || null }, 'Recepción confirmada. El Agente de Impacto registró el rescate.', TOKEN.receptor(recId))(ev), 'primario', 'check'))); })
        : el('p', { class: 'vacio' }, 'Nada pendiente.'),
      caminoHacia.length ? [subtitulo('En camino hacia ti', caminoHacia.length), caminoHacia.map((d) => tarea(`Donación #${d.id}`, d))] : null);
  }
  function pintarVoluntario() {
    const mias = donaciones.filter((d) => d.voluntario && d.voluntario.id === volId);
    const ruta = (d) => el('p', { class: 'sub' }, `Recoger en ${d.donante.nombre} y entregar en ${d.receptor.nombre} · ${d.ruta.km} km, ~${d.ruta.minutos} min · recoges ${d.ruta.recoger}, entregas ${d.ruta.entrega}`
      + (d.requiere_frio ? ' · lleva la hielera (cadena de frío)' : ''));
    const propuestas = mias.filter((d) => d.estado === 'asignada');
    const activas = mias.filter((d) => ['en_recoleccion', 'en_camino'].includes(d.estado));
    llenar(cVol,
      subtitulo('Propuestas de recolección', propuestas.length),
      propuestas.length ? propuestas.map((d) => tarea(`Propuesta · donación #${d.id}`, d, ruta(d), vence(d.propuesta_vence_en, 'La propuesta'), el('div', { class: 'fila' },
        boton('Aceptar recolección', accion(`/donaciones/${d.id}/voluntario`, { aceptar: true }, 'Recolección aceptada. El donante ya fue avisado.', TOKEN.voluntario(volId)), 'primario', 'check'),
        boton('Rechazar', accion(`/donaciones/${d.id}/voluntario`, { aceptar: false }, 'Rechazaste; el Logístico buscará otro voluntario.', TOKEN.voluntario(volId)), 'peligro')))) : el('p', { class: 'vacio' }, 'Sin propuestas.'),
      subtitulo('Mis recolecciones activas', activas.length),
      activas.length ? activas.map((d) => tarea(`Donación #${d.id}`, d, ruta(d),
        d.estado === 'en_recoleccion' ? boton('Ya recogí con el donante', accion(`/donaciones/${d.id}/avance`, { estado: 'recogida' }, 'Registrado: ya recogiste la donación.', TOKEN.voluntario(volId)), 'primario', 'paquete')
          : boton('Ya entregué en el receptor', accion(`/donaciones/${d.id}/avance`, { estado: 'entregada' }, 'Registrado: entregaste. Falta que el receptor confirme.', TOKEN.voluntario(volId)), 'primario', 'pin')))
        : el('p', { class: 'vacio' }, 'Nada en curso.'));
  }
  function pintarAdmin() {
    const porValidar = donaciones.filter((d) => d.estado === 'pendiente_validacion');
    const atoradas = donaciones.filter((d) => ['sin_receptor', 'sin_voluntario'].includes(d.estado));
    llenar(cAdm,
      subtitulo('Alimentos de riesgo por validar', porValidar.length),
      el('p', { class: 'sub', style: 'margin-bottom:.6rem' }, 'Carnes, lácteos y comida preparada no avanzan sin que una persona los apruebe.'),
      porValidar.length ? porValidar.map((d) => tarea(`Donación #${d.id}`, d, d.requiere_frio ? el('span', { class: 'chip info' }, 'Requiere cadena de frío') : null,
        el('div', { class: 'fila' }, boton('Aprobar', accion(`/donaciones/${d.id}/revision`, { aceptar: true }, 'Aprobada: el Coordinador ya busca receptor.', TOKEN.admin), 'primario', 'check'),
          boton('Rechazar', accion(`/donaciones/${d.id}/revision`, { aceptar: false }, 'Rechazada; se avisó al donante.', TOKEN.admin), 'peligro')))) : el('p', { class: 'vacio' }, 'Nada por validar.'),
      atoradas.length ? [subtitulo('Donaciones atoradas', atoradas.length), atoradas.map((d) => tarea(`Donación #${d.id}`, d, el('p', { class: 'sub' }, 'No hay receptor o voluntario viable. Revisa el detalle en “Seguimiento”.')))] : null,
      ctx.modoDemo ? [
        subtitulo('Controles de la demostración'),
        el('p', { class: 'sub', style: 'margin-bottom:.6rem' }, 'Borra las donaciones y conversaciones y recarga los datos de prueba.'),
        boton('Reiniciar datos de demo', (ev) => {
          if (!confirm('Se borrarán todas las donaciones y conversaciones. ¿Continuar?')) return undefined;
          return sinDobleClic(ev, '/demo/reiniciar', async () => {
            try { await POST('/demo/reiniciar', {}, TOKEN.admin); aviso('Datos de demostración recargados.', 'ok'); } catch (e) { aviso(e.message, 'error'); }
            firmas.clear(); await cargarDonaciones(); await Operacion.refrescar();
          });
        }, 'peligro', 'recargar')] : null);
  }
  return {
    async activar() {
      llenar(selRec, ctx.receptores.map((r) => el('option', { value: r.id }, r.nombre)));
      llenar(selVol, ctx.voluntarios.map((v) => el('option', { value: v.id }, `${v.nombre} · ${v.vehiculo}`)));
      if (!ctx.receptores.some((r) => r.id === recId)) recId = ctx.receptores[0].id;
      if (!ctx.voluntarios.some((v) => v.id === volId)) volId = ctx.voluntarios[0].id;
      selRec.value = recId; selVol.value = volId;
      firmas.clear();
      await this.refrescar();
    },
    async refrescar() {
      await cargarDonaciones();
      pintar('rec', [donaciones, recId], pintarReceptor);
      pintar('vol', [donaciones, volId], pintarVoluntario);
      pintar('adm', [donaciones, ctx.modoDemo], pintarAdmin);
    },
  };
})();

// ------------------------------------------------------------------------------------------ Impacto
const Impacto = (() => {
  const seccion = document.getElementById('vista-impacto');
  const cont = el('div');
  const PALETA = ['#3ddc84', '#5ab0ff', '#ffd166', '#b794f6', '#ff9f43', '#ff6b81', '#19b6a0', '#8fa3b8'];
  const KG_CO2E_POR_KM_AUTO = 0.25;  // auto compacto promedio, aproximado; solo para dar una referencia fácil de imaginar
  seccion.append(el('div', { class: 'impacto-cabeza' },
    el('div', null, el('span', { class: 'ceja' }, icono('hoja'), 'Agente de Impacto'), el('h1', null, 'Lo que ya ', el('span', { class: 'neon' }, 'rescatamos'))),
    el('p', { class: 'sub', style: 'max-width:28rem' }, 'Calculado con las recepciones que confirmaron los receptores, con los kilos que de verdad llegaron.')), cont);

  const kpi = (color, ic, valor, que, nota) => {
    const b = el('b', null, '0');
    contar(b, valor);
    return el('div', { class: 'tarjeta kpi', style: `--c:${color}` }, el('span', { class: 'avatar', style: `--c:${color}` }, icono(ic)), b, el('span', { class: 'que' }, que), el('div', { class: 'nota' }, nota));
  };
  function dona(filas) {
    if (!filas.length) return el('p', { class: 'vacio' }, 'Aún sin datos.');
    const total = filas.reduce((s, f) => s + f.kg, 0), R = 70, C = 2 * Math.PI * R;
    let acumulado = 0;
    const segmentos = filas.map((f, i) => {
      const largo = (f.kg / total) * C;
      const s = svg('circle', { class: 'segmento', cx: 95, cy: 95, r: R, fill: 'none', stroke: PALETA[i % PALETA.length], 'stroke-width': 22,
        'stroke-dasharray': `0 ${C}`, 'stroke-dashoffset': -acumulado, transform: 'rotate(-90 95 95)' });
      requestAnimationFrame(() => requestAnimationFrame(() => s.setAttribute('stroke-dasharray', `${Math.max(largo - 2, 0.5)} ${C}`)));
      acumulado += largo;
      return s;
    });
    return el('div', { class: 'dona' },
      svg('svg', { viewBox: '0 0 190 190', role: 'img', 'aria-label': 'Kilos rescatados por tipo de alimento' },
        svg('circle', { cx: 95, cy: 95, r: R, fill: 'none', stroke: '#213129', 'stroke-width': 22 }), segmentos,
        svg('text', { x: 95, y: 92, 'text-anchor': 'middle', fill: '#e7f1ec', 'font-size': 28, 'font-weight': 800 }, num(total)),
        svg('text', { x: 95, y: 114, 'text-anchor': 'middle', fill: '#93a79d', 'font-size': 12 }, 'kg en total')),
      el('ul', { class: 'leyenda-dona' }, filas.map((f, i) => el('li', { style: `--c:${PALETA[i % PALETA.length]}` },
        el('i'), el('span', null, f.etiqueta), el('span', null, `${num(f.kg)} kg · ${Math.round((100 * f.kg) / total)} %`)))));
  }
  function barras(filas) {
    if (!filas.length) return el('p', { class: 'vacio' }, 'Aún sin datos.');
    return filas.map((f) => {
      const i = el('i');
      requestAnimationFrame(() => requestAnimationFrame(() => { i.style.width = `${(100 * f.kg) / filas[0].kg}%`; }));
      return el('div', { class: 'fila-barra' }, el('span', null, f.etiqueta), el('span', { class: 'pista' }, i), el('span', null, `${num(f.kg)} kg`));
    });
  }
  return {
    async activar() { firmas.delete('impacto'); await this.refrescar(); },
    async refrescar() {
      const r = await GET('/impacto');
      pintar('impacto', r, () => {
        const t = r.totales, s = r.supuestos;
        llenar(cont,
          el('div', { class: 'kpis' },
            kpi('var(--neon)', 'paquete', t.kg, 'kg rescatados', `${t.rescates} ${t.rescates === 1 ? 'rescate completado' : 'rescates completados'}`),
            kpi('var(--amarillo)', 'plato', t.raciones, 'raciones', `1 ración = ${s.kg_por_racion} kg de alimento`),
            kpi('var(--captador)', 'grupo', t.personas, 'personas alimentadas un día', `${s.raciones_por_persona_dia} raciones por persona al día (est.)`),
            kpi('var(--neon-2)', 'nube', t.co2e_kg, 'kg de CO2e evitados', 'factores por tipo de alimento, por validar')),
          el('div', { class: 'equivalencias' },
            el('div', { class: 'equivalencia' }, el('span', { class: 'avatar', style: '--c:var(--neon)' }, icono('auto')),
              el('div', null, el('b', null, `≈ ${num(t.co2e_kg / KG_CO2E_POR_KM_AUTO)} km`), el('p', null, `que un auto dejó de recorrer, en emisiones (≈ ${KG_CO2E_POR_KM_AUTO} kg de CO2e por km)`))),
            el('div', { class: 'equivalencia' }, el('span', { class: 'avatar', style: '--c:var(--amarillo)' }, icono('corazon')),
              el('div', null, el('b', null, t.rescates ? `${num(t.personas / t.rescates)} personas` : '—'), el('p', null, 'alimentadas un día, en promedio, por cada rescate'))),
            el('div', { class: 'equivalencia' }, el('span', { class: 'avatar', style: '--c:var(--captador)' }, icono('pin')),
              el('div', null, el('b', null, `${r.por_municipio.length} ${r.por_municipio.length === 1 ? 'municipio' : 'municipios'}`), el('p', null, 'de la zona metropolitana ya donaron')))),
          el('div', { class: 'rejilla' },
            el('div', { class: 'tarjeta' }, el('h3', null, 'Por tipo de alimento'), dona(r.por_categoria)),
            el('div', { class: 'tarjeta' }, el('h3', null, 'Por municipio de origen'), barras(r.por_municipio))),
          el('div', { class: 'tarjeta', style: 'margin-top:1rem' }, el('h3', null, 'Últimos rescates'),
            r.ultimos.length ? el('div', { class: 'envoltura' }, el('table', null, el('thead', null, el('tr', null, ['Donación', 'Donante', 'Receptor', 'kg', 'Raciones', 'CO2e'].map((h) => el('th', null, h)))),
              el('tbody', null, r.ultimos.map((u) => el('tr', null, el('td', null, `#${u.id}`), el('td', null, u.donante), el('td', null, u.receptor), el('td', null, el('b', null, num(u.kg))), el('td', null, num(u.raciones)), el('td', null, `${num(u.co2e_kg)} kg`))))))
              : el('p', { class: 'vacio' }, 'Completa un rescate en la demo para verlo aquí.')),
          el('p', { class: 'sub', style: 'margin-top:1rem' }, 'Los supuestos (raciones por kilo, raciones por persona, factores de CO2e) son editables y están pendientes de validar con un banco de alimentos real.'));
      });
    },
  };
})();

// ------------------------------------------------------------------------------------------ arranque
async function cargarDonaciones() { donaciones = await GET('/donaciones'); }
const vistas = { inicio: Inicio, donar: Donar, seguimiento: Seguimiento, operacion: Operacion, impacto: Impacto };
let actual = null;

async function activar(nombre, param) {
  if (!vistas[nombre]) nombre = 'inicio';
  actual = nombre;
  for (const s of document.querySelectorAll('main > section')) s.hidden = s.id !== `vista-${nombre}`;
  for (const a of document.querySelectorAll('.pestanas a')) { if (a.getAttribute('href') === `#${nombre}`) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  window.scrollTo({ top: 0 });
  try { await vistas[nombre].activar(param); } catch (e) { aviso(`No se pudo cargar la vista: ${e.message}`, 'error'); }
}
async function actualizarEstado() {
  const e = await GET('/estado');
  ctx.pesos = e.pesos;
  ctx.modoDemo = e.modo_demo;
  llenar(document.getElementById('estado-app'), el('span', null, el('i', { class: 'punto' }), e.reloj_de_demo ? 'Hora de demo ' : 'Hora ', el('b', null, e.hora.slice(11, 16))),
    el('span', null, e.modo_demo ? 'Demo' : 'Normal'));
  const nota = document.querySelector('.aviso');
  if (nota) nota.textContent = e.modo_demo ? 'Modo demostración: cada pestaña actúa con un usuario de prueba.'
    : 'El servidor no está en modo demostración: los usuarios de prueba no tienen permisos. Arráncalo con python -m comparte --demo.';
}
async function iniciar() {
  for (const a of document.querySelectorAll('.pestanas a[data-icono]')) a.prepend(icono(a.dataset.icono));
  try {
    [ctx.donantes, ctx.receptores, ctx.voluntarios] = await Promise.all([GET('/donantes'), GET('/receptores'), GET('/voluntarios')]);
    await actualizarEstado();
  } catch (e) {
    document.querySelector('main').append(el('div', { class: 'tarjeta' }, el('h2', null, 'No pude conectar con la API'), el('p', null, `Arranca el servidor con: python -m comparte. Detalle: ${e.message}`)));
    return;
  }
  const enrutar = () => { const [n, p] = (location.hash || '#inicio').slice(1).split('/'); activar(n, p); };
  window.addEventListener('hashchange', enrutar);
  enrutar();
  setInterval(async () => { if (document.hidden || !actual) return; try { await actualizarEstado(); await vistas[actual].refrescar(); } catch (e) { /* reintenta en el siguiente ciclo */ } }, 3000);
}
iniciar();
