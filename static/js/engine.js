// RecycleMeter calculation engine. Pure functions only: no DOM, no network.
// Mirrors src/recyclemeter/engine.py. Factors come from data/factors.json and are
// never taken from user input.

export const MAX_KG = 1e9;
export const MONTHS_PER_YEAR = 12;

export class ValidationError extends Error {
  constructor(issues) {
    super(issues.join('; '));
    this.name = 'ValidationError';
    this.issues = issues;
  }
}

/** Strict numeric parse. Blank or malformed input gives NaN. Thousands separators are allowed. */
export function parseQuantity(raw) {
  if (typeof raw === 'number') return raw;
  const s = String(raw ?? '').trim().replace(/[,\s]/g, '');
  if (s === '' || !/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(s)) return NaN;
  return Number(s);
}

export function findMaterial(registry, id) {
  const m = registry.materials.find((x) => x.id === id);
  if (!m) throw new ValidationError(['Choose a plastic type.']);
  return m;
}

export function toKg(quantity, unit, registry) {
  if (unit === 'kg') return quantity;
  if (unit === 'lb') return quantity * registry.units.kg_per_lb;
  throw new ValidationError([`Unknown unit: ${unit}`]);
}

export function validate(input, registry) {
  const issues = [];
  const q = input.quantity;
  const unitOk = ['kg', 'lb'].includes(input.unit);
  if (!unitOk) issues.push('Choose kilograms or pounds.');
  if (typeof q !== 'number' || !Number.isFinite(q)) issues.push('Enter the weight as a number.');
  else if (q <= 0) issues.push('Weight must be greater than zero.');
  else if (unitOk && toKg(q, input.unit, registry) > MAX_KG) issues.push('That weight is larger than this calculator accepts.');
  if (!registry.materials.some((m) => m.id === input.material)) issues.push('Choose a plastic type.');
  if (!['once', 'monthly'].includes(input.timeframe ?? 'once')) issues.push('Choose one-time or monthly.');
  return issues;
}

export function equivalencies(co2Kg, registry) {
  const e = registry.equivalencies;
  return {
    trees: co2Kg / e.tree_kg_per_year.value,
    petrolLitres: co2Kg / e.petrol_kg_per_litre.value,
    phoneCharges: co2Kg * e.phone_charges_per_kg.value,
  };
}

export function calculate(input, registry) {
  const issues = validate(input, registry);
  if (issues.length) throw new ValidationError(issues);
  const material = findMaterial(registry, input.material);
  const massKg = toKg(input.quantity, input.unit, registry);
  const co2Kg = massKg * material.multiplier;
  const timeframe = input.timeframe ?? 'once';
  return {
    material,
    massKg,
    multiplier: material.multiplier,
    co2Kg,
    annualCo2Kg: timeframe === 'monthly' ? co2Kg * MONTHS_PER_YEAR : null,
    ...equivalencies(co2Kg, registry),
    timeframe,
    registryVersion: registry.registry_version,
  };
}

/** Deterministic report reference (FNV-1a over canonical inputs). Mirrors calc_reference(). */
export function calcReference(input, registry, date) {
  const mass = toKg(input.quantity, input.unit, registry);
  const canon = [registry.registry_version, input.material, input.timeframe ?? 'once', mass.toFixed(6), date].join('|');
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(canon)) {
    h ^= byte;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `RM-${date.replaceAll('-', '')}-${h.toString(16).toUpperCase().padStart(8, '0')}`;
}

/* ---------- formatting (presentation only) ---------- */

const nf = (min, max) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: min, maximumFractionDigits: max });

/** CO2 mass: kg below one tonne, tonnes above. Returns { value, unit }. */
export function formatMass(kg) {
  if (!Number.isFinite(kg)) return { value: '–', unit: 'kg' };
  if (Math.abs(kg) >= 1000) return { value: nf(2, 2).format(kg / 1000), unit: 'tonnes' };
  if (Math.abs(kg) >= 100) return { value: nf(1, 1).format(kg), unit: 'kg' };
  return { value: nf(2, 2).format(kg), unit: 'kg' };
}

/** Everyday counts: whole numbers when large, one or two decimals when small. */
export function formatCount(n) {
  if (!Number.isFinite(n)) return '–';
  if (n >= 100) return nf(0, 0).format(Math.round(n));
  if (n >= 10) return nf(0, 1).format(n);
  return nf(0, 2).format(n);
}

export function formatQuantity(n) {
  return nf(0, 3).format(n);
}

export const todayISO = () => {
  const d = new Date();
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
