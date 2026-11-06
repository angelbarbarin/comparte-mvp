// Interfaz de ComParte (MVP): JavaScript sin dependencias ni compilación, salvo Leaflet para el mapa.
// Todo texto entra como nodo de texto (nunca innerHTML con datos): un mensaje con HTML no puede inyectar código.
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

async function api(metodo, ruta, cuerpo) {
  const r = await fetch('/api' + ruta, { method: metodo, headers: cuerpo === undefined ? {} : { 'Content-Type': 'application/json' }, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (!r.ok) throw new Error(datos && typeof datos.detail === 'string' ? datos.detail : 'Los datos enviados no son válidos');
  return datos;
}
const GET = (ruta) => api('GET', ruta);
const POST = (ruta, cuerpo = {}) => api('POST', ruta, cuerpo);

function aviso(texto, tipo = '') {
  const n = el('div', { class: tipo }, texto);
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

const AGENTES = { captador: 'Agente Captador', coordinador: 'Agente Coordinador', logistico: 'Agente Logístico', impacto: 'Agente de Impacto', orquestador: 'Orquestador', humano: 'Persona', donante: 'Donante' };
const insignia = (a) => el('span', { class: 'insignia', style: `background:var(--${a === 'donante' ? 'donante' : a})` }, AGENTES[a] || a);
const ESTADOS = {
  registrada: ['Registrada', 'info'], pendiente_validacion: ['En revisión humana', 'alerta'], rechazada: ['Rechazada', 'error'],
  ofrecida: ['Ofrecida a un receptor', 'info'], sin_receptor: ['Sin receptor', 'error'], asignada: ['Receptor aceptó', 'info'],
  sin_voluntario: ['Sin voluntario', 'error'], en_recoleccion: ['Voluntario va por ella', 'info'], en_camino: ['En camino al receptor', 'info'],
  entregada: ['Entregada · falta confirmar', 'alerta'], completada: ['Completada', 'ok'],
};
const chipEstado = (e) => el('span', { class: `chip ${(ESTADOS[e] || [])[1] || ''}` }, (ESTADOS[e] || [e])[0]);

function pasos(d) {
  const nombres = ['Registrada', ...(d.requiere_revision ? ['Revisión humana'] : []), 'Receptor', 'Voluntario', 'Recolección', 'Entrega', 'Completada'];
  const i = (n) => nombres.indexOf(n);
  const activo = { registrada: 0, pendiente_validacion: i('Revisión humana'), rechazada: i('Revisión humana'), ofrecida: i('Receptor'), sin_receptor: i('Receptor'),
    asignada: i('Voluntario'), sin_voluntario: i('Voluntario'), en_recoleccion: i('Recolección'), en_camino: i('Entrega'), entregada: i('Completada'), completada: nombres.length }[d.estado] ?? 0;
  const fallo = ['sin_receptor', 'sin_voluntario', 'rechazada'].includes(d.estado);
  return el('ol', { class: 'pasos', 'aria-label': 'Progreso de la donación' },
    nombres.map((n, k) => el('li', { class: k < activo ? 'hecho' : k === activo ? (fallo ? 'fallo' : 'activo') : '' }, n)));
}

const ctx = { donantes: [], receptores: [], voluntarios: [], pesos: {} };
let donaciones = [];

// ------------------------------------------------------------------------------------------ Donar
const Donar = (() => {
  const seccion = document.getElementById('vista-donar');
  let donanteId = prefs.leer('donanteId', null);
  const selector = el('select', { id: 'donante', onchange: () => { donanteId = Number(selector.value); prefs.guardar('donanteId', donanteId); firmas.delete('chat'); Donar.refrescar(); } });
  const mensajes = el('div', { class: 'mensajes', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversación con el Agente Captador' });
  const entrada = el('input', { type: 'text', id: 'texto', placeholder: 'Describe lo que sobró: qué, cuánto y hasta cuándo…', autocomplete: 'off', maxlength: 2000, 'aria-label': 'Mensaje' });
  const panel = el('div');
  const EJEMPLOS = [
    ['Pan del día y fruta', 'Tengo 25 kg de pan dulce del día y 10 kg de fruta madura'],
    ['Pollo y leche (riesgo)', 'Tengo 12 kg de pollo y 8 litros de leche, vence mañana'],
    ['Falta la cantidad', 'Tengo pan dulce'],
    ['Alimento no aceptado', 'Tengo 10 litros de cerveza'],
  ];
  seccion.append(el('div', { class: 'rejilla' },
    el('div', { class: 'tarjeta' },
      el('h2', null, 'Habla con el Agente Captador'),
      el('p', { class: 'sub' }, 'Cuéntale tu excedente como a una persona. Se confirma antes de registrarlo.'),
      el('div', { class: 'fila', style: 'margin:.7rem 0' },
        el('div', { class: 'campo' }, el('label', { for: 'donante' }, 'Actuar como donante'), selector),
        el('button', { class: 'boton', type: 'button', onclick: nueva }, 'Nueva conversación')),
      el('div', { class: 'chat' }, mensajes,
        el('form', { onsubmit: enviar }, entrada, el('button', { class: 'boton primario', type: 'submit' }, 'Enviar'))),
      el('div', { class: 'ejemplos' }, el('span', { class: 'sub' }, 'Ejemplos para la demo:'),
        EJEMPLOS.map(([t, x]) => el('button', { class: 'chip boton', type: 'button', onclick: () => { entrada.value = x; entrada.focus(); } }, t)))),
    el('div', null,
      el('div', { class: 'tarjeta' }, el('h2', null, 'Tu donación'), panel),
      el('div', { class: 'tarjeta' }, el('h3', null, '¿Quién hace qué?'),
        el('ul', { class: 'sub', style: 'padding-left:1.1rem;margin:0;display:grid;gap:.4rem' },
          el('li', null, insignia('captador'), ' entiende tu mensaje y revisa la inocuidad.'),
          el('li', null, insignia('coordinador'), ' elige el receptor que más lo necesita y llega a tiempo.'),
          el('li', null, insignia('logistico'), ' busca voluntario y calcula la ruta.'),
          el('li', null, insignia('impacto'), ' mide kg, raciones, personas y CO2e.'),
          el('li', null, insignia('orquestador'), ' los coordina y pide revisión humana si hay riesgo.'))))));

  async function enviar(ev) {
    ev.preventDefault();
    const texto = entrada.value.trim();
    if (!texto) return;
    try {
      const r = await POST(`/chat/${donanteId}`, { texto });
      entrada.value = '';
      pintarChat(r.mensajes);
      if (r.donacion_id) aviso(`Donación #${r.donacion_id} registrada. Sigue su avance en “Seguimiento”.`, 'ok');
      await cargarDonaciones();
      pintarPanel();
    } catch (e) { aviso(e.message, 'error'); }
  }
  async function nueva() { pintarChat((await POST(`/chat/${donanteId}/nueva`)).mensajes); }
  function pintarChat(lista) {
    pintar('chat', lista, (ms) => {
      const abajo = mensajes.scrollHeight - mensajes.scrollTop - mensajes.clientHeight < 80;
      llenar(mensajes, ms.map((m) => el('div', { class: `msj ${m.rol === 'donante' ? 'mio' : ''}` },
        el('div', { class: 'quien' }, m.rol === 'donante' ? 'Tú' : insignia(m.rol)), el('div', { class: 'globo' }, m.texto))));
      if (abajo || ms.length <= 1) mensajes.scrollTop = mensajes.scrollHeight;
    });
  }
  function pintarPanel() {
    const d = donaciones.find((x) => x.donante.id === donanteId);
    pintar('panel', d || null, () => llenar(panel, d ? [
      el('div', { class: 'fila entre' }, el('b', null, `Donación #${d.id}`), chipEstado(d.estado)),
      el('p', { class: 'sub', style: 'margin:.3rem 0' }, `${textoItems(d.items)} · ${kg(d.total_kg)}`), pasos(d),
      d.receptor ? el('p', { style: 'margin-top:.5rem' }, 'Receptor: ', el('b', null, d.receptor.nombre)) : null,
      el('button', { class: 'boton', style: 'margin-top:.6rem', onclick: () => { location.hash = `#seguimiento/${d.id}`; } }, 'Ver seguimiento completo'),
    ] : el('p', { class: 'vacio' }, 'Cuando confirmes tu donación verás aquí su avance.')));
  }
  return {
    async activar() {
      llenar(selector, ctx.donantes.map((d) => el('option', { value: d.id }, `${d.nombre} · ${d.municipio}`)));
      if (!ctx.donantes.some((d) => d.id === donanteId)) donanteId = ctx.donantes[0].id;
      selector.value = donanteId;
      firmas.clear();
      await this.refrescar();
    },
    async refrescar() { await cargarDonaciones(); pintarChat((await GET(`/chat/${donanteId}`)).mensajes); pintarPanel(); },
  };
})();

// ------------------------------------------------------------------------------------- Seguimiento
const Seguimiento = (() => {
  const seccion = document.getElementById('vista-seguimiento');
  let sel = null, mapa = null, capa = null, firmaMapa = null;
  const lista = el('ul', { class: 'lista' });
  const detalle = el('div');
  const mapaDiv = el('div', { id: 'mapa', role: 'img', 'aria-label': 'Mapa con donante, receptor y voluntario' });
  seccion.append(el('div', { class: 'rejilla doc' }, el('div', { class: 'tarjeta' }, el('h2', null, 'Donaciones'), lista), detalle));
  const COMP = [['necesidad', 'Necesidad', '#1d4f91'], ['cercania', 'Cercanía', '#6b3fb5'], ['capacidad', 'Capacidad', '#17663f']];

  function dato(n, v) { return el('div', null, el('div', { class: 'sub' }, n), el('b', null, v)); }
  function tablaReceptores(d) {
    if (!d.evaluacion || !d.evaluacion.length) return el('p', { class: 'vacio' }, 'Aún no se evalúan receptores (la donación espera revisión).');
    return el('div', null, el('div', { class: 'envoltura' }, el('table', null,
      el('thead', null, el('tr', null, el('th', null, 'Receptor'), el('th', null, 'Puntaje'), el('th', null, 'Resultado'))),
      el('tbody', null, d.evaluacion.map((c) => el('tr', { class: c.viable ? '' : 'descartado' },
        el('td', null, el('b', null, c.nombre), el('div', { class: 'sub' }, `${c.distancia_km} km · llegaría ${c.llegada}`)),
        el('td', null, c.viable ? [el('b', null, c.puntaje.toFixed(0)), ' / 100',
          el('div', { class: 'barra' }, COMP.map(([k, n, col]) => el('i', { title: `${n}: ${Math.round(100 * c.componentes[k])} %`, style: `width:${100 * (d_pesos(k)) * c.componentes[k]}%;background:${col}` })))] : `${c.puntaje.toFixed(0)} (ref.)`),
        el('td', null, c.viable ? el('span', { class: 'chip ok' }, 'Viable') : [el('span', { class: 'chip error' }, 'Descartado'), el('ul', { class: 'sub', style: 'margin:.3rem 0 0;padding-left:1rem' }, c.motivos.map((m) => el('li', null, m)))])))))),
      el('div', { class: 'leyenda' }, COMP.map(([k, n, col]) => el('span', { style: `--c:${col}` }, `${n} (${Math.round(100 * d_pesos(k))} %)`))));
  }
  const d_pesos = (k) => ctx.pesos[k] || 0;

  function pintarMapa(d) {
    if (!window.L) { mapaDiv.textContent = 'No se pudo cargar el mapa (¿sin conexión?). El resto de la demo funciona igual.'; return; }
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
    const colores = { donante: '#b45309', receptor: '#17663f', voluntario: '#1d4f91' };
    const pts = [];
    const marca = (rol, a, etiqueta) => { const p = [a.lat, a.lon]; pts.push(p); L.circleMarker(p, { radius: 9, color: '#fff', weight: 2, fillColor: colores[rol], fillOpacity: 1 }).bindTooltip(`${etiqueta}: ${a.nombre}`).addTo(capa); return p; };
    const pd = marca('donante', d.donante, 'Donante');
    const pr = d.receptor ? marca('receptor', d.receptor, 'Receptor') : null;
    if (d.voluntario) { const pv = marca('voluntario', d.voluntario, 'Voluntario'); L.polyline([pv, pd], { color: '#1d4f91', weight: 3, dashArray: '6 6' }).addTo(capa); }
    if (pr) L.polyline([pd, pr], { color: '#17663f', weight: 4 }).addTo(capa);
    if (otra) mapa.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 14 });
  }

  function pintarDetalle(d) {
    llenar(detalle,
      el('div', { class: 'tarjeta' },
        el('div', { class: 'fila entre' }, el('h2', null, `Donación #${d.id} · ${d.donante.nombre}`), chipEstado(d.estado)),
        el('div', { class: 'kpis', style: 'margin:.6rem 0 0' }, dato('Alimentos', textoItems(d.items)), dato('Peso total', kg(d.total_kg)),
          dato('Caduca', d.caduca_en.replace('T', ' ')), dato('Receptor', d.receptor ? d.receptor.nombre : '—'),
          dato('Voluntario', d.voluntario ? `${d.voluntario.nombre} (${d.voluntario.vehiculo})` : '—'),
          dato('Ruta', d.ruta && d.ruta.km ? `${d.ruta.km} km · ~${d.ruta.minutos} min` : '—')),
        pasos(d)),
      el('div', { class: 'tarjeta' }, el('h3', null, 'Mapa y ruta'), mapaDiv,
        el('p', { class: 'sub', style: 'margin-top:.4rem' }, 'Naranja: donante · Verde: receptor · Azul: voluntario. Distancias estimadas (línea recta x 1.3): el MVP no usa API de mapas.')),
      el('div', { class: 'tarjeta' }, el('div', { class: 'fila' }, insignia('coordinador'), el('h3', null, 'Cómo eligió al receptor')),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .5rem' }, 'Puntaje 0-100 = necesidad + cercanía + capacidad. Cada descarte conserva su motivo.'), tablaReceptores(d)),
      el('div', { class: 'tarjeta' }, el('h3', null, 'Línea de tiempo de los agentes'),
        el('p', { class: 'sub', style: 'margin:.2rem 0 .5rem' }, 'Cada decisión y cada traspaso del orquestador queda registrado.'),
        d.eventos.length ? el('ol', { class: 'linea' }, d.eventos.map((e) => el('li', null, el('time', null, e.hora), insignia(e.agente), el('span', null, e.resumen)))) : el('p', { class: 'vacio' }, 'Sin eventos.')));
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
          el('b', null, `#${d.id} · ${d.donante.nombre}`), el('span', { class: 'sub' }, `${textoItems(d.items)} · ${kg(d.total_kg)}`), chipEstado(d.estado))))
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
  seccion.append(el('div', { class: 'rejilla' },
    el('div', null,
      el('div', { class: 'tarjeta' }, el('h2', null, 'Receptor'), el('label', null, 'Actuar como'), selRec, cRec),
      el('div', { class: 'tarjeta' }, el('h2', null, 'Voluntario'), el('label', null, 'Actuar como'), selVol, cVol)),
    el('div', { class: 'tarjeta' }, el('h2', null, 'Administrador'), cAdm)));

  async function accion(ruta, cuerpo, ok) {
    try { await POST(ruta, cuerpo); aviso(ok, 'ok'); } catch (e) { aviso(e.message, 'error'); }
    firmas.clear();
    await Operacion.refrescar();
  }
  const boton = (t, fn, clase = '') => el('button', { class: `boton ${clase}`, type: 'button', onclick: fn }, t);
  const tarea = (titulo, d, ...extra) => el('div', { class: 'tarea' }, el('div', { class: 'fila entre' }, el('b', null, titulo), chipEstado(d.estado)),
    el('p', null, el('b', null, textoItems(d.items)), ` · ${kg(d.total_kg)} de ${d.donante.nombre}`), ...extra);

  function pintarReceptor() {
    const mias = donaciones.filter((d) => d.receptor && d.receptor.id === recId);
    const ofertas = mias.filter((d) => d.estado === 'ofrecida'), porConfirmar = mias.filter((d) => d.estado === 'entregada');
    const caminoHacia = mias.filter((d) => ['asignada', 'en_recoleccion', 'en_camino'].includes(d.estado));
    llenar(cRec,
      el('h3', { style: 'margin-top:.8rem' }, 'Ofertas por responder'),
      ofertas.length ? ofertas.map((d) => tarea(`Oferta · donación #${d.id}`, d, el('p', { class: 'sub' }, `Caduca ${d.caduca_en.replace('T', ' ')}`),
        el('div', { class: 'fila' }, boton('Aceptar', () => accion(`/donaciones/${d.id}/receptor`, { aceptar: true }, 'Aceptaste la donación. El Logístico buscará quién la recoja.'), 'primario'),
          boton('Rechazar', () => accion(`/donaciones/${d.id}/receptor`, { aceptar: false }, 'Rechazaste la oferta; el Coordinador buscará otro receptor.'), 'peligro')))) : el('p', { class: 'vacio' }, 'Sin ofertas por ahora.'),
      el('h3', { style: 'margin-top:.8rem' }, 'Por confirmar recepción'),
      porConfirmar.length ? porConfirmar.map((d) => { const entrada = el('input', { type: 'number', min: '0.1', step: '0.1', value: d.total_kg, 'aria-label': 'Kilos realmente recibidos' });
        return tarea(`Donación #${d.id} entregada`, d, el('div', { class: 'fila' }, el('div', { class: 'campo' }, el('label', null, 'Kilos que recibiste (corrígelos si difieren)'), entrada),
          boton('Confirmar recepción', () => accion(`/donaciones/${d.id}/confirmacion`, { kg_recibidos: Number(entrada.value) || null }, 'Recepción confirmada. El Agente de Impacto registró el rescate.'), 'primario'))); })
        : el('p', { class: 'vacio' }, 'Nada pendiente.'),
      caminoHacia.length ? [el('h3', { style: 'margin-top:.8rem' }, 'En camino hacia ti'), caminoHacia.map((d) => tarea(`Donación #${d.id}`, d))] : null);
  }
  function pintarVoluntario() {
    const mias = donaciones.filter((d) => d.voluntario && d.voluntario.id === volId);
    const ruta = (d) => el('p', { class: 'sub' }, `Recoger en ${d.donante.nombre} y entregar en ${d.receptor.nombre} · ${d.ruta.km} km, ~${d.ruta.minutos} min · recoges ${d.ruta.recoger}, entregas ${d.ruta.entrega}`
      + (d.requiere_frio ? ' · lleva la hielera (cadena de frío)' : ''));
    const propuestas = mias.filter((d) => d.estado === 'asignada');
    llenar(cVol,
      el('h3', { style: 'margin-top:.8rem' }, 'Propuestas de recolección'),
      propuestas.length ? propuestas.map((d) => tarea(`Propuesta · donación #${d.id}`, d, ruta(d), el('div', { class: 'fila' },
        boton('Aceptar recolección', () => accion(`/donaciones/${d.id}/voluntario`, { aceptar: true }, 'Recolección aceptada. El donante ya fue avisado.'), 'primario'),
        boton('Rechazar', () => accion(`/donaciones/${d.id}/voluntario`, { aceptar: false }, 'Rechazaste; el Logístico buscará otro voluntario.'), 'peligro')))) : el('p', { class: 'vacio' }, 'Sin propuestas.'),
      el('h3', { style: 'margin-top:.8rem' }, 'Mis recolecciones activas'),
      mias.filter((d) => ['en_recoleccion', 'en_camino'].includes(d.estado)).map((d) => tarea(`Donación #${d.id}`, d, ruta(d),
        d.estado === 'en_recoleccion' ? boton('Ya recogí con el donante', () => accion(`/donaciones/${d.id}/avance`, { estado: 'recogida' }, 'Registrado: ya recogiste la donación.'), 'primario')
          : boton('Ya entregué en el receptor', () => accion(`/donaciones/${d.id}/avance`, { estado: 'entregada' }, 'Registrado: entregaste. Falta que el receptor confirme.'), 'primario'))));
  }
  function pintarAdmin() {
    const porValidar = donaciones.filter((d) => d.estado === 'pendiente_validacion');
    const atoradas = donaciones.filter((d) => ['sin_receptor', 'sin_voluntario'].includes(d.estado));
    llenar(cAdm,
      el('h3', null, 'Alimentos de riesgo por validar'),
      el('p', { class: 'sub', style: 'margin-bottom:.5rem' }, 'Carnes, lácteos y comida preparada no avanzan sin que una persona los apruebe.'),
      porValidar.length ? porValidar.map((d) => tarea(`Donación #${d.id}`, d, d.requiere_frio ? el('span', { class: 'chip info' }, 'Requiere cadena de frío') : null,
        el('div', { class: 'fila' }, boton('Aprobar', () => accion(`/donaciones/${d.id}/revision`, { aceptar: true }, 'Aprobada: el Coordinador ya busca receptor.'), 'primario'),
          boton('Rechazar', () => accion(`/donaciones/${d.id}/revision`, { aceptar: false }, 'Rechazada; se avisó al donante.'), 'peligro')))) : el('p', { class: 'vacio' }, 'Nada por validar.'),
      atoradas.length ? [el('h3', { style: 'margin-top:1rem' }, 'Donaciones atoradas'), atoradas.map((d) => tarea(`Donación #${d.id}`, d, el('p', { class: 'sub' }, 'No hay receptor o voluntario viable. Revisa el detalle en “Seguimiento”.')))] : null,
      el('h3', { style: 'margin-top:1rem' }, 'Controles de la demostración'),
      el('p', { class: 'sub', style: 'margin-bottom:.5rem' }, 'Borra las donaciones y conversaciones y recarga los datos de prueba.'),
      boton('Reiniciar datos de demo', async () => {
        if (!confirm('Se borrarán todas las donaciones y conversaciones. ¿Continuar?')) return;
        await POST('/demo/reiniciar'); firmas.clear(); await cargarDonaciones(); aviso('Datos de demostración recargados.', 'ok'); await Operacion.refrescar();
      }, 'peligro'));
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
      pintar('adm', donaciones, pintarAdmin);
    },
  };
})();

// ------------------------------------------------------------------------------------------ Impacto
const Impacto = (() => {
  const seccion = document.getElementById('vista-impacto');
  const cont = el('div');
  seccion.append(cont);
  const kpi = (v, n, nota) => el('div', { class: 'kpi' }, el('b', null, v), el('span', null, n), nota ? el('div', { class: 'sub' }, nota) : null);
  const barras = (filas) => filas.length ? filas.map((f) => el('div', { class: 'fila-barra' }, el('span', null, f.etiqueta),
    el('span', { class: 'pista' }, el('i', { style: `width:${100 * f.kg / filas[0].kg}%` })), el('span', null, `${num(f.kg)} kg`))) : el('p', { class: 'vacio' }, 'Aún sin datos.');
  return {
    async activar() { firmas.clear(); await this.refrescar(); },
    async refrescar() {
      const r = await GET('/impacto');
      pintar('impacto', r, () => {
        const t = r.totales, s = r.supuestos;
        llenar(cont,
          el('div', { class: 'tarjeta' }, el('h2', null, 'Impacto del rescate'), el('p', { class: 'sub' }, 'Calculado por el Agente de Impacto con las recepciones confirmadas por los receptores.')),
          el('div', { class: 'kpis', style: 'margin-top:1rem' },
            kpi(num(t.kg), 'kg rescatados', `${t.rescates} rescates`), kpi(num(t.raciones), 'raciones', `1 ración = ${s.kg_por_racion} kg`),
            kpi(num(t.personas), 'personas beneficiadas (est.)', `raciones ÷ ${s.raciones_por_persona_dia}: personas alimentadas un día`), kpi(num(t.co2e_kg), 'kg de CO2e evitados', 'factores por validar')),
          el('div', { class: 'rejilla' },
            el('div', { class: 'tarjeta' }, el('h3', null, 'Por tipo de alimento'), barras(r.por_categoria)),
            el('div', { class: 'tarjeta' }, el('h3', null, 'Por municipio de origen'), barras(r.por_municipio))),
          el('div', { class: 'tarjeta', style: 'margin-top:1rem' }, el('h3', null, 'Últimos rescates'),
            r.ultimos.length ? el('div', { class: 'envoltura' }, el('table', null, el('thead', null, el('tr', null, ['Donación', 'Donante', 'Receptor', 'kg', 'Raciones', 'CO2e'].map((h) => el('th', null, h)))),
              el('tbody', null, r.ultimos.map((u) => el('tr', null, el('td', null, `#${u.id}`), el('td', null, u.donante), el('td', null, u.receptor), el('td', null, num(u.kg)), el('td', null, num(u.raciones)), el('td', null, `${num(u.co2e_kg)} kg`))))))
              : el('p', { class: 'vacio' }, 'Completa un rescate en la demo para verlo aquí.')),
          el('p', { class: 'sub', style: 'margin-top:1rem' }, 'Los supuestos (raciones por kilo, raciones por persona, factores de CO2e) son editables y están pendientes de validar con un banco de alimentos real.'));
      });
    },
  };
})();

// ------------------------------------------------------------------------------------------ arranque
async function cargarDonaciones() { donaciones = await GET('/donaciones'); }
const vistas = { donar: Donar, seguimiento: Seguimiento, operacion: Operacion, impacto: Impacto };
let actual = null;

async function activar(nombre, param) {
  if (!vistas[nombre]) nombre = 'donar';
  actual = nombre;
  for (const s of document.querySelectorAll('main > section')) s.hidden = s.id !== `vista-${nombre}`;
  for (const a of document.querySelectorAll('.pestanas a')) { if (a.getAttribute('href') === `#${nombre}`) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  try { await vistas[nombre].activar(param); } catch (e) { aviso(`No se pudo cargar la vista: ${e.message}`, 'error'); }
}
async function actualizarEstado() {
  const e = await GET('/estado');
  ctx.pesos = e.pesos;
  llenar(document.getElementById('estado-app'), el('span', null, e.reloj_de_demo ? 'Hora de demo: ' : 'Hora: ', el('b', null, e.hora.slice(11, 16))), el('span', null, 'Datos de demostración'));
}
async function iniciar() {
  try {
    [ctx.donantes, ctx.receptores, ctx.voluntarios] = await Promise.all([GET('/donantes'), GET('/receptores'), GET('/voluntarios')]);
    await actualizarEstado();
  } catch (e) {
    document.querySelector('main').append(el('div', { class: 'tarjeta' }, el('h2', null, 'No pude conectar con la API'), el('p', null, `Arranca el servidor con: python -m comparte. Detalle: ${e.message}`)));
    return;
  }
  const enrutar = () => { const [n, p] = (location.hash || '#donar').slice(1).split('/'); activar(n, p); };
  window.addEventListener('hashchange', enrutar);
  enrutar();
  setInterval(async () => { if (document.hidden || !actual) return; try { await actualizarEstado(); await vistas[actual].refrescar(); } catch (e) { /* reintenta en el siguiente ciclo */ } }, 3000);
}
iniciar();
