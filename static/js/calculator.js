import { calculate, findMaterial, formatCount, formatMass, formatQuantity, parseQuantity, todayISO, validate } from './engine.js';

const $ = (s) => document.querySelector(s);
const form = $('#calc-form');
const qty = $('#quantity');
const errs = $('#quantity-errors');
const meter = $('#meter');
const SVGNS = 'http://www.w3.org/2000/svg';

let registry;
let calculated = false;

/* ---------- gauge (log scale, 1 kg to 100 t CO2e) ---------- */
const C = { x: 160, y: 168, r: 128 };
const DECADES = 5;
const fraction = (kg) => (kg >= 1 ? Math.min(Math.log10(kg) / DECADES, 1) : 0);

function buildGauge() {
  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    parent?.appendChild(n);
    return n;
  };
  const svg = el('svg', { viewBox: '0 0 320 180' });
  const arc = `M${C.x - C.r} ${C.y} A${C.r} ${C.r} 0 0 1 ${C.x + C.r} ${C.y}`;
  el('path', { d: arc, class: 'track', fill: 'none', 'stroke-width': 18, 'stroke-linecap': 'round', pathLength: 100 }, svg);
  el('path', { d: arc, class: 'fill', id: 'gauge-fill', fill: 'none', 'stroke-width': 18, 'stroke-linecap': 'round', pathLength: 100, 'stroke-dasharray': '0 100' }, svg);
  ['1', '10', '100', '1k', '10k', '100k'].forEach((label, i) => {
    const a = Math.PI * (1 - i / DECADES);
    const p = (rr) => [C.x + rr * Math.cos(a), C.y - rr * Math.sin(a)];
    const [x1, y1] = p(C.r - 20), [x2, y2] = p(C.r - 14), [lx, ly] = p(C.r - 32);
    el('line', { x1, y1, x2, y2, class: 'tick' }, svg);
    const t = el('text', { x: lx, y: ly + 3.5, 'text-anchor': 'middle', class: 'tick-label' }, svg);
    t.textContent = label;
  });
  const needle = el('g', { class: 'needle', id: 'gauge-needle' }, svg);
  el('line', { x1: C.x, y1: C.y, x2: C.x - (C.r - 44), y2: C.y }, needle);
  el('circle', { cx: C.x, cy: C.y, r: 9, class: 'hub-ring' }, svg);
  el('circle', { cx: C.x, cy: C.y, r: 3.5, class: 'hub' }, svg);
  $('#gauge').appendChild(svg);
}

function setGauge(kg) {
  const f = fraction(kg);
  $('#gauge-fill').setAttribute('stroke-dasharray', `${(f * 100).toFixed(2)} 100`);
  $('#gauge-needle').style.transform = `rotate(${(f * 180).toFixed(2)}deg)`;
}

/* ---------- state ---------- */
const radio = (name) => form.querySelector(`input[name="${name}"]:checked`).value;
const setRadio = (name, v) => { const r = form.querySelector(`input[name="${name}"][value="${v}"]`); if (r) r.checked = true; };

function readInput() {
  return { material: $('#material').value, quantity: parseQuantity(qty.value), unit: radio('unit'), timeframe: radio('timeframe') };
}

function reportHref(input) {
  const p = new URLSearchParams({ m: input.material, q: String(input.quantity), u: input.unit, t: input.timeframe, d: todayISO() });
  return `report.html#${p}`;
}

function setLinks(href) {
  for (const id of ['#report-link', '#report-cta']) {
    const a = $(id);
    if (href) { a.href = href; a.removeAttribute('aria-disabled'); }
    else { a.href = id === '#report-link' ? '#impact-reports' : '#calculator'; a.setAttribute('aria-disabled', 'true'); }
  }
  $('#report-cta-hint').textContent = href ? 'Opens a printable report for your latest calculation.' : 'Run a calculation first.';
}

function showEmpty(message) {
  meter.classList.add('is-empty');
  $('#readout-label').textContent = 'Prevented';
  setGauge(0);
  $('#co2-value').textContent = '0';
  $('#co2-unit').textContent = 'kg CO₂e';
  $('#co2-context').innerHTML = message;
  $('#annual').hidden = true;
  for (const id of ['#trees', '#petrol', '#phones']) $(id).textContent = '–';
  $('#compare').hidden = true;
  setLinks(null);
}

function renderCompare(res, input) {
  const m = res.material;
  if (m.ef_virgin == null) { $('#compare').hidden = true; return; }
  const v = res.massKg * m.ef_virgin, r = res.massKg * m.ef_recycled;
  const fm = (x) => { const f = formatMass(x); return `${f.value} ${f.unit}`; };
  $('#compare-sub').textContent = `${formatQuantity(input.quantity)} ${input.unit === 'lb' ? 'lbs' : 'kg'} of ${m.label}, kg CO₂e`;
  $('#bars').innerHTML = `
    <div class="bar-row"><span>Virgin ${m.label}</span><span class="bar"><i class="v" style="width:100%"></i></span><span class="val">${fm(v)}</span></div>
    <div class="bar-row"><span>Recycled ${m.label}</span><span class="bar"><i class="r" style="width:${((r / v) * 100).toFixed(1)}%"></i></span><span class="val">${fm(r)}</span></div>
    <div class="bar-row saving"><span>Emissions avoided</span><span></span><span class="val">${fm(v - r)}</span></div>`;
  $('#compare-note').textContent = `Producing ${m.label} from recycled material emits about ${Math.round((1 - m.ef_recycled / m.ef_virgin) * 100)}% less than producing it from virgin feedstock (${m.ef_virgin} vs ${m.ef_recycled} kg CO₂e per kg).`;
  $('#compare').hidden = false;
}

function render() {
  const input = readInput();
  const material = findMaterial(registry, input.material);
  $('#material-hint').textContent = `${material.name ? material.name + '. ' : ''}${material.examples}.`;
  qty.removeAttribute('aria-invalid');
  errs.innerHTML = '';
  if (!calculated) return;

  const issues = validate(input, registry);
  if (issues.length) {
    qty.setAttribute('aria-invalid', 'true');
    errs.innerHTML = issues.map((i) => `<li>${i}</li>`).join('');
    showEmpty('Fix the weight above to see your impact.');
    return;
  }
  const res = calculate(input, registry);
  const total = formatMass(res.co2Kg);
  meter.classList.remove('is-empty');
  $('#readout-label').textContent = res.timeframe === 'monthly' ? 'Prevented per month' : 'Prevented';
  setGauge(res.co2Kg);
  $('#co2-value').textContent = total.value;
  $('#co2-unit').textContent = `${total.unit} CO₂e`;
  const per = res.timeframe === 'monthly' ? ' every month' : '';
  $('#co2-context').textContent =
    `${formatQuantity(input.quantity)} ${input.unit === 'lb' ? 'lbs' : 'kg'} of ${material.label} recycled${per}, at ${res.multiplier} kg CO₂e saved per kg.`;
  if (res.annualCo2Kg !== null) {
    const a = formatMass(res.annualCo2Kg);
    $('#annual').innerHTML = `Over a year: <b>${a.value} ${a.unit} CO₂e</b> prevented`;
    $('#annual').hidden = false;
  } else $('#annual').hidden = true;
  $('#trees').textContent = formatCount(res.trees);
  $('#petrol').textContent = formatCount(res.petrolLitres);
  $('#phones').textContent = formatCount(res.phoneCharges);
  renderCompare(res, input);
  setLinks(reportHref(input));
}

/* ---------- mechanical-recycling badge tooltip (hover, focus, or tap) ---------- */
function watchTooltip() {
  const mech = $('.mech'), btn = $('.mech-badge');
  const set = (open) => { mech.classList.toggle('open', open); mech.classList.remove('dismissed'); btn.setAttribute('aria-expanded', String(open)); };
  btn.addEventListener('click', (e) => { e.stopPropagation(); set(!mech.classList.contains('open')); });
  document.addEventListener('click', (e) => { if (!mech.contains(e.target)) set(false); });
  // Escape hides it even while hovered or focused (WCAG 1.4.13); it shows again on the next hover.
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { set(false); mech.classList.add('dismissed'); } });
  mech.addEventListener('mouseenter', () => mech.classList.remove('dismissed'));
  btn.addEventListener('blur', () => mech.classList.remove('dismissed'));
  // Open towards whichever side has room, so the tooltip never runs off-screen.
  const place = () => {
    const b = btn.getBoundingClientRect(), w = $('#mech-tip').offsetWidth;
    mech.classList.toggle('align-left', b.right - w < 8 && b.left + w <= document.documentElement.clientWidth - 8);
  };
  ['mouseenter', 'focusin', 'pointerdown'].forEach((ev) => mech.addEventListener(ev, place));
  window.addEventListener('resize', place);
  place();
}

/* ---------- navigation highlight ---------- */
function watchSections() {
  const links = new Map([...document.querySelectorAll('.nav a')].map((a) => [a.hash.slice(1), a]));
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach((a) => a.removeAttribute('aria-current'));
      links.get(e.target.id)?.setAttribute('aria-current', 'location');
    }
  }, { rootMargin: '-45% 0px -50% 0px' });
  links.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
}

/* ---------- restore from a report's "back" link ---------- */
function restore() {
  if (!location.hash.startsWith('#m=')) return;
  const p = new URLSearchParams(location.hash.slice(1));
  if (registry.materials.some((m) => m.id === p.get('m'))) $('#material').value = p.get('m');
  if (p.get('q')) qty.value = p.get('q');
  setRadio('unit', p.get('u'));
  setRadio('timeframe', p.get('t'));
  calculated = true;
  history.replaceState(null, '', location.pathname + '#calculator');
}

async function init() {
  // Stop an early click on "Calculate" from reloading the page while the factors are still loading.
  form.addEventListener('submit', (e) => e.preventDefault());
  buildGauge();
  watchSections();
  watchTooltip();
  try {
    const r = await fetch('data/factors.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(String(r.status));
    registry = await r.json();
  } catch {
    $('#co2-context').textContent = 'The calculator could not load its emission factors. Start the site with "python manage.py serve".';
    return;
  }
  restore();
  showEmpty('Enter a weight and select <b>Calculate impact</b>.');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    calculated = true;
    render();
    if (!validate(readInput(), registry).length && window.matchMedia('(max-width: 60rem)').matches) {
      meter.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    }
  });
  form.addEventListener('input', render);
  form.addEventListener('change', render);
  for (const id of ['#report-link', '#report-cta']) {
    $(id).addEventListener('click', (e) => {
      if ($(id).getAttribute('aria-disabled') === 'true') { e.preventDefault(); qty.focus(); }
    });
  }
  render();
}
init();
