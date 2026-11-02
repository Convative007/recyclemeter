import { calculate, calcReference, formatCount, formatMass, formatQuantity, todayISO, validate } from './engine.js';

const $ = (s) => document.querySelector(s);
const root = $('#report');
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const REFERENCES = [
  'Association of Plastic Recyclers (APR) & Franklin Associates. (2020). Life Cycle Impacts for Postconsumer Recycled Resins: PET, HDPE, and PP. More Than Chem. LLC & Eastern Research Group.',
  'Chilton, T., Burnley, S., & Nesaratnam, S. (2010). A life cycle assessment of the closed-loop recycling and thermal recovery of post-consumer PET. Resources, Conservation and Recycling, 54(12), 1241–1249.',
  'Chin, H. H., et al. (2022). Plastic Circular Economy Framework using Hybrid Machine Learning and Pinch Analysis. Resources, Conservation and Recycling, 184, 106387.',
  'Faraca, G., & Astrup, T. (2019). Plastic waste from households: Composition, recycling performance and carbon footprint. Waste Management, 95, 388–398. https://doi.org/10.1016/j.wasman.2019.06.028',
  'Gandhi, N., et al. (2021). Life Cycle Assessment of Recycling High-Density Polyethylene Plastic Waste. Journal of Renewable Materials, 9, 1463–1483.',
  'Nordahl, S. L., & Scown, C. D. (2024). Recommendations for life-cycle assessment of recyclable plastics in a circular economy. Chemical Science, 15, 9397–9407.',
];

function fail(msg) {
  root.innerHTML = `<div class="fail"><h1 style="font-size:1.5rem;margin-bottom:.75rem">Report unavailable</h1><p class="muted">${msg}</p><p><a href="index.html#calculator">Go to the calculator</a> to create one.</p></div>`;
}

// Icons are copied from the page's own sprite so the report and calculator stay identical.
const iconFrom = (name) => document.querySelector(`template#icon-${name}`)?.innerHTML ?? '';

async function init() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (!p.has('m')) return fail('This link does not contain a calculation.');
  let registry;
  try { registry = await (await fetch('data/factors.json', { cache: 'no-store' })).json(); }
  catch { return fail('The emission factors could not be loaded.'); }

  const input = { material: p.get('m'), quantity: Number(p.get('q')), unit: p.get('u'), timeframe: p.get('t') || 'once' };
  const issues = validate(input, registry);
  if (issues.length) return fail(esc(issues.join(' ')));

  const date = /^\d{4}-\d{2}-\d{2}$/.test(p.get('d') || '') ? p.get('d') : todayISO();
  const res = calculate(input, registry);
  const ref = calcReference(input, registry, date);
  const m = res.material;
  const total = formatMass(res.co2Kg);
  const annual = res.annualCo2Kg !== null ? formatMass(res.annualCo2Kg) : null;
  const unitLabel = input.unit === 'lb' ? 'lbs' : 'kg';
  const eq = registry.equivalencies;
  const longDate = new Date(`${date}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });

  root.innerHTML = `
    <header class="report-head">
      <div>
        <div class="brand">${document.querySelector('.topbar .brand').innerHTML}</div>
        <h1>Plastic recycling impact report</h1>
      </div>
      <div class="ref"><b>${esc(ref)}</b>${esc(longDate)}<br>Factor set v${esc(registry.registry_version)}</div>
    </header>

    <section>
      <h2>Total CO&#8322; emissions prevented</h2>
      <div class="report-total"><b>${total.value}</b><span>${total.unit} CO&#8322;e</span></div>
      <p class="muted" style="margin:.5rem 0 0">${formatQuantity(input.quantity)} ${unitLabel}${input.unit === 'lb' ? ` (${formatQuantity(res.massKg)} kg)` : ''} of ${esc(m.label)} recycled${res.timeframe === 'monthly' ? ' every month' : ', one-time'}.
      ${annual ? `<br>Over a year: <b>${annual.value} ${annual.unit} CO&#8322;e</b>.` : ''}</p>
    </section>

    <section>
      <h2>Everyday equivalents</h2>
      <div class="dash">
        <div class="card metric"><span class="badge">${iconFrom('tree')}</span><span class="n">${formatCount(res.trees)}</span><span class="what">Trees planted equivalent</span><span class="how">CO&#8322; &divide; ${eq.tree_kg_per_year.value}</span></div>
        <div class="card metric"><span class="badge">${iconFrom('fuel')}</span><span class="n">${formatCount(res.petrolLitres)}</span><span class="what">Litres of petrol not burned</span><span class="how">CO&#8322; &divide; ${eq.petrol_kg_per_litre.value}</span></div>
        <div class="card metric"><span class="badge">${iconFrom('phone')}</span><span class="n">${formatCount(res.phoneCharges)}</span><span class="what">Smartphone charges powered</span><span class="how">CO&#8322; &times; ${eq.phone_charges_per_kg.value}</span></div>
      </div>
    </section>

    <section>
      <h2>Calculation</h2>
      <div class="scroll-x"><table><tbody>
        <tr><th scope="row">Plastic type</th><td class="r">${esc(m.label)}${m.name && m.id !== 'MIXED' ? ` (${esc(m.name)})` : ''}</td></tr>
        <tr><th scope="row">Weight recycled</th><td class="r">${formatQuantity(res.massKg)} kg</td></tr>
        ${m.ef_virgin != null ? `<tr><th scope="row">Emission factor, virgin</th><td class="r">${m.ef_virgin} kg CO&#8322;e/kg</td></tr>
        <tr><th scope="row">Emission factor, recycled</th><td class="r">${m.ef_recycled} kg CO&#8322;e/kg</td></tr>` : ''}
        <tr><th scope="row">Net saving per kg</th><td class="r">${m.multiplier} kg CO&#8322;e/kg</td></tr>
        <tr><th scope="row">CO&#8322; prevented</th><td class="r key">${formatQuantity(res.massKg)} &times; ${m.multiplier} = ${total.value} ${total.unit}</td></tr>
        ${annual ? `<tr><th scope="row">Annual (&times; 12)</th><td class="r">${annual.value} ${annual.unit}</td></tr>` : ''}
      </tbody></table></div>
      <p class="note">Formula: CO&#8322; saved (kg) = weight recycled (kg) &times; (EF<sub>virgin</sub> &minus; EF<sub>recycled</sub>).${input.unit === 'lb' ? ` Pounds converted at 1 lb = ${registry.units.kg_per_lb} kg.` : ''}</p>
    </section>

    <footer class="report-foot">
      <p><b>Methodology &amp; Sources.</b> Emissions reduction calculations are aligned with the principles of the US EPA Waste Reduction Model (WARM) and ISO 14044/14067 Life Cycle Assessment standards. Equivalency metrics are calculated using the US EPA Greenhouse Gas Equivalencies methodology.</p>
      <p style="margin-bottom:.4rem">Academic References:</p>
      <ul>${REFERENCES.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>
      <p>Results are indicative estimates based on average emission factors. They are not a certified carbon footprint of any product or organisation. Reference ${esc(ref)} can be reproduced from the same inputs, date and factor set.</p>
    </footer>`;

  const record = {
    reference: ref, date, tool: 'RecycleMeter', factor_set_version: registry.registry_version,
    inputs: { plastic_type: m.label, weight: input.quantity, unit: input.unit, timeframe: res.timeframe },
    weight_kg: res.massKg,
    factors: { ef_virgin: m.ef_virgin, ef_recycled: m.ef_recycled, net_saving_per_kg: m.multiplier },
    results: {
      co2_prevented_kg: res.co2Kg, annual_co2_prevented_kg: res.annualCo2Kg,
      trees_planted_equivalent: res.trees, petrol_litres_not_burned: res.petrolLitres, smartphone_charges: res.phoneCharges,
    },
    equivalency_constants: Object.fromEntries(Object.entries(eq).map(([k, v]) => [k, v.value])),
    formula: registry.formula,
    references: REFERENCES,
  };

  for (const id of ['#print', '#download', '#copy']) $(id).hidden = false;
  $('#print').addEventListener('click', () => window.print());
  $('#back').href = `index.html#${new URLSearchParams({ m: input.material, q: String(input.quantity), u: input.unit, t: res.timeframe })}`;
  $('#download').addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' }));
    a.download = `${ref}.json`;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $('#copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); $('#copy-status').textContent = 'Link copied.'; }
    catch { $('#copy-status').textContent = 'Copy the address from your browser bar.'; }
  });
  document.title = `${ref} | RecycleMeter impact report`;
}
init();
