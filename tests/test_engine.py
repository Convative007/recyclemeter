"""Acceptance tests for the RecycleMeter reference engine (factor set v2.x)."""
import json
import math
from pathlib import Path

import pytest

from recyclemeter.engine import ValidationError, calc_reference, calculate, find_material, to_kg

VECTORS = json.loads((Path(__file__).parent / "vectors.json").read_text())
BASE = {"material": "PET", "quantity": 100, "unit": "kg", "timeframe": "once"}


def test_published_multipliers(registry):
    expected = {"PET": 1.7, "HDPE": 1.1, "PP": 1.1, "MIXED": 1.3}
    assert {m["id"]: m["multiplier"] for m in registry["materials"]} == expected


@pytest.mark.parametrize("mid", ["PET", "HDPE", "PP"])
def test_multiplier_is_virgin_minus_recycled(registry, mid):
    m = find_material(registry, mid)
    assert m["ef_virgin"] - m["ef_recycled"] == pytest.approx(m["multiplier"])


def test_equivalency_constants(registry):
    e = registry["equivalencies"]
    assert (e["tree_kg_per_year"]["value"], e["petrol_kg_per_litre"]["value"], e["phone_charges_per_kg"]["value"]) == (21.7, 2.3, 121)


def test_pounds_conversion(registry):
    assert to_kg(1, "lb", registry) == 0.453592


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: f"{c['input']['material']}-{c['input']['quantity']}{c['input']['unit']}")
def test_vectors(registry, case):
    r = calculate(case["input"], registry)
    e, tol = case["expected"], VECTORS["tolerance_rel"]
    assert r.mass_kg == pytest.approx(e["mass_kg"], rel=tol)
    assert r.co2_kg == pytest.approx(e["co2_kg"], rel=tol)
    assert r.trees == pytest.approx(e["trees"], rel=tol)
    assert r.petrol_litres == pytest.approx(e["petrol_litres"], rel=tol)
    assert r.phone_charges == pytest.approx(e["phone_charges"], rel=tol)
    assert (r.annual_co2_kg is None) if e["annual_kg"] is None else r.annual_co2_kg == pytest.approx(e["annual_kg"], rel=tol)


def test_worked_example(registry):
    r = calculate(BASE, registry)  # 100 kg PET
    assert r.co2_kg == pytest.approx(170)
    assert r.trees == pytest.approx(7.834, abs=1e-3)
    assert r.petrol_litres == pytest.approx(73.913, abs=1e-3)
    assert r.phone_charges == pytest.approx(20570)


def test_monthly_is_twelve_times_one_period(registry):
    once = calculate(BASE, registry)
    monthly = calculate({**BASE, "timeframe": "monthly"}, registry)
    assert monthly.co2_kg == once.co2_kg and monthly.annual_co2_kg == pytest.approx(once.co2_kg * 12)


@pytest.mark.parametrize("bad", [0, -1, -0.001, math.nan, math.inf, None, "10", True, 1e12])
def test_rejects_bad_weight(registry, bad):
    with pytest.raises(ValidationError):
        calculate({**BASE, "quantity": bad}, registry)


@pytest.mark.parametrize("field,value", [("material", "PVC"), ("unit", "tonne"), ("timeframe", "weekly")])
def test_rejects_unknown_choices(registry, field, value):
    with pytest.raises(ValidationError):
        calculate({**BASE, field: value}, registry)


def test_reference_is_deterministic_and_input_sensitive(registry):
    a = calc_reference(BASE, registry, "2026-11-02")
    assert a == calc_reference(BASE, registry, "2026-11-02") and a.startswith("RM-20261102-")
    assert a != calc_reference({**BASE, "quantity": 101}, registry, "2026-11-02")
    assert a != calc_reference(BASE, registry, "2026-11-03")
