"""Static site build: renders Jinja templates and the factor registry into dist/."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .engine import calculate, load_registry

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DATA = ROOT / "data"
DIST = ROOT / "dist"

PAGES = {
    "index.html": "index.html",
    "report.html": "report.html",
    "404.html": "not_found.html",
}


def build(dist: Path = DIST) -> Path:
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    registry = load_registry()
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(STATIC, dist / "assets")
    (dist / "data").mkdir()
    shutil.copy(DATA / "factors.json", dist / "data" / "factors.json")

    example_input = {"material": "PET", "quantity": 100.0, "unit": "kg", "timeframe": "once"}
    ctx = {
        "site": site,
        "registry": registry,
        "example": {"input": example_input, "result": calculate(example_input, registry)},
        "app_version": __version__,
        "build_date": date.today().isoformat(),
    }
    for out_name, tpl_name in PAGES.items():
        html = env.get_template(tpl_name).render(page=out_name, **ctx)
        (dist / out_name).write_text(html, encoding="utf-8")
    return dist
