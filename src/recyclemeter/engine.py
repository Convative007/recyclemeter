"""Reference implementation of the RecycleMeter calculation.

The browser runs static/js/engine.js. This module mirrors it so both can be checked
against the same test vectors and the maths can be audited without a browser.
Factors come from data/factors.json only; they are never accepted from the caller.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "factors.json"

MAX_KG = 1e9
MONTHS_PER_YEAR = 12


class ValidationError(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_material(registry: dict, material_id: str) -> dict:
    for m in registry["materials"]:
        if m["id"] == material_id:
            return m
    raise ValidationError(["Choose a plastic type."])


def to_kg(quantity: float, unit: str, registry: dict) -> float:
    if unit == "kg":
        return quantity
    if unit == "lb":
        return quantity * registry["units"]["kg_per_lb"]
    raise ValidationError([f"Unknown unit: {unit!r}"])


def validate(inp: dict, registry: dict) -> None:
    issues: list[str] = []
    q = inp.get("quantity")
    unit = inp.get("unit")
    if unit not in {"kg", "lb"}:
        issues.append("Choose kilograms or pounds.")
    if isinstance(q, bool) or not isinstance(q, (int, float)) or not math.isfinite(q):
        issues.append("Enter the weight as a number.")
    elif q <= 0:
        issues.append("Weight must be greater than zero.")
    elif unit in {"kg", "lb"} and to_kg(q, unit, registry) > MAX_KG:
        issues.append("That weight is larger than this calculator accepts.")
    if inp.get("material") not in {m["id"] for m in registry["materials"]}:
        issues.append("Choose a plastic type.")
    if inp.get("timeframe", "once") not in {"once", "monthly"}:
        issues.append("Choose one-time or monthly.")
    if issues:
        raise ValidationError(issues)


@dataclass
class Result:
    mass_kg: float
    multiplier: float
    co2_kg: float
    annual_co2_kg: float | None
    trees: float
    petrol_litres: float
    phone_charges: float
    timeframe: str
    registry_version: str


def equivalencies(co2_kg: float, registry: dict) -> dict:
    e = registry["equivalencies"]
    return {
        "trees": co2_kg / e["tree_kg_per_year"]["value"],
        "petrol_litres": co2_kg / e["petrol_kg_per_litre"]["value"],
        "phone_charges": co2_kg * e["phone_charges_per_kg"]["value"],
    }


def calculate(inp: dict, registry: dict) -> Result:
    validate(inp, registry)
    material = find_material(registry, inp["material"])
    mass = to_kg(inp["quantity"], inp["unit"], registry)
    co2 = mass * material["multiplier"]
    timeframe = inp.get("timeframe", "once")
    eq = equivalencies(co2, registry)
    return Result(
        mass_kg=mass,
        multiplier=material["multiplier"],
        co2_kg=co2,
        annual_co2_kg=co2 * MONTHS_PER_YEAR if timeframe == "monthly" else None,
        trees=eq["trees"],
        petrol_litres=eq["petrol_litres"],
        phone_charges=eq["phone_charges"],
        timeframe=timeframe,
        registry_version=registry["registry_version"],
    )


def calc_reference(inp: dict, registry: dict, date: str) -> str:
    """Deterministic report reference. Must match calcReference() in engine.js."""
    mass = to_kg(inp["quantity"], inp["unit"], registry)
    canon = "|".join([registry["registry_version"], inp["material"], inp.get("timeframe", "once"), f"{mass:.6f}", date])
    h = 0x811C9DC5
    for byte in canon.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"RM-{date.replace('-', '')}-{h:08X}"
