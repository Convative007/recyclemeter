"""Runs the real JavaScript engine and the page in Chromium."""
import json
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from recyclemeter.engine import calc_reference  # noqa: E402

VECTORS = json.loads((Path(__file__).parent / "vectors.json").read_text())


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser, site_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield pg
    ctx.close()
    assert not errors, errors


def calc(page, material="PET", qty="100", unit="kg", timeframe="once"):
    page.select_option("#material", material)
    page.fill("#quantity", qty)
    page.check(f"input[name=unit][value={unit}]", force=True)
    page.check(f"input[name=timeframe][value={timeframe}]", force=True)
    page.click("button[type=submit]")


def test_js_engine_matches_vectors(page, site_url):
    page.goto(site_url + "/index.html")
    out = page.evaluate(
        """async (cases) => {
          const E = await import('/assets/js/engine.js');
          const reg = await (await fetch('/data/factors.json')).json();
          return cases.map(c => E.calculate(c.input, reg));
        }""", VECTORS["cases"])
    for got, case in zip(out, VECTORS["cases"]):
        e = case["expected"]
        for k_js, k_py in [("massKg", "mass_kg"), ("co2Kg", "co2_kg"), ("trees", "trees"), ("petrolLitres", "petrol_litres"), ("phoneCharges", "phone_charges")]:
            assert got[k_js] == pytest.approx(e[k_py], rel=1e-9), (case["input"], k_js)
        assert got["annualCo2Kg"] == (pytest.approx(e["annual_kg"], rel=1e-9) if e["annual_kg"] is not None else None)


def test_js_reference_matches_python(page, site_url, registry):
    page.goto(site_url + "/index.html")
    v = VECTORS["reference_case"]
    js = page.evaluate("""async (v) => { const E = await import('/assets/js/engine.js');
        const reg = await (await fetch('/data/factors.json')).json(); return E.calcReference(v.input, reg, v.date); }""", v)
    assert js == calc_reference(v["input"], registry, v["date"])


def test_calculate_shows_expected_outputs(page, site_url):
    page.goto(site_url + "/index.html")
    assert page.inner_text("#co2-value") == "0" and page.inner_text("#trees") == "–"
    calc(page)
    assert page.inner_text("#co2-value") == "170.0"
    assert page.inner_text("#trees") == "7.83"
    assert page.inner_text("#petrol") == "73.9"
    assert page.inner_text("#phones") == "20,570"
    assert "70.0 kg" in page.inner_text("#bars") or "110.0 kg" in page.inner_text("#bars")


def test_monthly_lbs_and_tonnes(page, site_url):
    page.goto(site_url + "/index.html")
    calc(page, material="MIXED", qty="12500", unit="lb", timeframe="monthly")
    # 12,500 lb x 0.453592 x 1.3 = 7,370.87 kg -> 7.37 tonnes; x12 = 88.45 tonnes
    assert page.inner_text("#co2-value") == "7.37" and "tonnes" in page.inner_text("#co2-unit")
    assert "88.45 tonnes" in page.inner_text("#annual")
    assert page.is_hidden("#compare")  # mixed plastics has no virgin/recycled breakdown


@pytest.mark.parametrize("value", ["0", "-4", "abc", ""])
def test_rejects_bad_weight_in_ui(page, site_url, value):
    page.goto(site_url + "/index.html")
    calc(page, qty=value)
    assert page.get_attribute("#quantity", "aria-invalid") == "true"
    assert page.inner_text("#co2-value") == "0"
    assert page.get_attribute("#report-link", "aria-disabled") == "true"


def test_report_reproduces_screen_and_downloads(page, site_url, registry):
    page.goto(site_url + "/index.html")
    calc(page, material="HDPE", qty="37.5", unit="lb", timeframe="monthly")
    screen = [page.inner_text(s) for s in ("#co2-value", "#trees", "#petrol", "#phones")]
    page.click("#report-link")
    page.wait_for_selector(".report-total")
    report = [page.inner_text(".report-total b")] + [x.inner_text() for x in page.locator(".report .metric .n").all()]
    assert report == screen
    text = page.inner_text("#report")
    assert "RM-" in text and "Academic References" in text
    for ref in ["Association of Plastic Recyclers", "Chilton", "Chin", "Faraca", "Gandhi", "Nordahl"]:
        assert ref in text, ref
    with page.expect_download() as dl:
        page.click("#download")
    record = json.loads(Path(dl.value.path()).read_text())
    assert record["factor_set_version"] == registry["registry_version"]
    assert record["results"]["co2_prevented_kg"] == pytest.approx(37.5 * 0.453592 * 1.1)


def test_report_back_link_restores_calculation(page, site_url):
    page.goto(site_url + "/report.html#m=PP&q=40&u=kg&t=monthly&d=2026-11-02")
    page.wait_for_selector(".report-total")
    page.click("#back")
    page.wait_for_function("document.querySelector('#co2-value').textContent !== '0'")
    assert page.inner_text("#co2-value") == "44.00"
    assert page.input_value("#material") == "PP"


def test_bad_report_link(page, site_url):
    page.goto(site_url + "/report.html#m=PP&q=-3&u=kg&t=once")
    page.wait_for_selector(".fail h1")
    assert "Report unavailable" in page.inner_text("#report")


def test_page_has_required_content(page, site_url):
    page.goto(site_url + "/index.html")
    body = page.inner_text("body")
    for needed in ["How It Works", "Impact Reports", "About RecycleMeter",
                   "Methodology & Sources", "Faraca, G., & Astrup, T. (2019)", "Association of Plastic Recyclers (APR) & Franklin Associates. (2020)", "aligned with the principles of the US EPA Waste Reduction Model (WARM) and ISO 14044/14067"]:
        assert needed in body, needed


@pytest.mark.parametrize("path", ["index.html", "report.html#m=PET&q=100&u=kg&t=monthly&d=2026-11-02"])
def test_no_horizontal_scroll_on_phone(browser, site_url, path):
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(f"{site_url}/{path}")
    if path == "index.html":
        pg.fill("#quantity", "123456"); pg.click("button[type=submit]")
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    ctx.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("path", ["index.html", "report.html#m=PET&q=100&u=kg&t=monthly&d=2026-11-02", "404.html"])
def test_wcag_aa(browser, site_url, path, scheme):
    axe_mod = pytest.importorskip("axe_playwright_python.sync_playwright")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme)
    pg = ctx.new_page()
    pg.goto(f"{site_url}/{path}")
    if path == "index.html":
        pg.fill("#quantity", "250"); pg.check("input[name=timeframe][value=monthly]", force=True); pg.click("button[type=submit]")
    pg.wait_for_timeout(400)
    res = axe_mod.Axe().run(pg, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}})
    ctx.close()
    violations = [(v["id"], [n["target"] for n in v["nodes"]][:3], v["nodes"][0].get("failureSummary", "")[:140]) for v in res.response["violations"]]
    assert not violations, violations


def test_email_in_contact_section(page, site_url):
    page.goto(site_url + "/index.html")
    contact = page.locator("#contact")
    assert "Email us at impact@recyclemeter.org" in contact.inner_text()
    assert contact.locator("a").get_attribute("href") == "mailto:impact@recyclemeter.org"
    assert page.get_attribute(".nav a:has-text('Contact')", "href") == "index.html#contact"


def test_methodology_accordion_opens_with_scope_callout(page, site_url):
    page.goto(site_url + "/index.html")
    acc = page.locator("#methodology-science")
    assert acc.locator("summary").inner_text() == "Methodology & Science"
    assert not page.locator("#system-scope").is_visible()
    acc.locator("summary").click()
    assert page.locator("#system-scope").is_visible()
    assert page.evaluate("document.querySelector('#methodology-science .body').firstElementChild.id") == "system-scope"
    text = page.inner_text("#system-scope")
    assert text.startswith("System Scope & Recycling Methodology")
    assert "closed-loop mechanical recycling" in text and "pyrolysis or gasification" in text
    assert "standardized" not in text and "following the principles of ISO 14044/14067" in text


def test_mechanical_badge_tooltip(page, site_url):
    page.goto(site_url + "/index.html")
    tip = page.locator("#mech-tip")
    assert page.inner_text(".mech-badge") == "Mechanical Recycling Baseline"
    assert not tip.is_visible()
    page.hover(".mech-badge"); page.wait_for_timeout(250)
    assert tip.is_visible() and "rather than thermal pyrolysis or chemical recycling" in tip.inner_text()
    page.mouse.move(0, 0)
    page.click(".mech-badge"); page.wait_for_timeout(250)
    assert tip.is_visible() and page.get_attribute(".mech-badge", "aria-expanded") == "true"
    page.keyboard.press("Escape"); page.mouse.move(0, 0); page.wait_for_timeout(250)
    assert not tip.is_visible()


@pytest.mark.parametrize("width", [360, 390, 1280])
def test_tooltip_stays_on_screen(browser, site_url, width):
    ctx = browser.new_context(viewport={"width": width, "height": 800}, is_mobile=width < 500, has_touch=width < 500)
    pg = ctx.new_page()
    pg.goto(site_url + "/index.html")
    (pg.tap if width < 500 else pg.click)(".mech-badge")
    pg.wait_for_timeout(250)
    box = pg.locator("#mech-tip").bounding_box()
    ctx.close()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width


def test_results_footnote_at_bottom(page, site_url):
    page.goto(site_url + "/index.html")
    note = page.locator(".results-footnote")
    assert note.inner_text().startswith("*Net savings reflect cradle-to-gate mechanical recycling inventories")
    assert "Data source:" not in note.inner_text()
    # last element of the calculator section, after the equivalents and the virgin-vs-recycled card
    assert page.evaluate("document.querySelector('#calculator > .wrap').lastElementChild.className") == "results-footnote"


def test_undone_prompt_content_absent(page, site_url):
    page.goto(site_url + "/index.html")
    html = page.content()
    assert 'class="org"' not in html
    for gone in ["Circular by design", "Chaturanga", "Infinitely Circular", "⚙"]:
        assert gone.lower() not in html.lower(), gone


def test_early_submit_does_not_reload(browser, site_url):
    """Clicking Calculate before the factor file arrives must not reload the page."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    release = []
    pg.route("**/data/factors.json", lambda route, req: release.append(route))
    pg.goto(site_url + "/index.html", wait_until="domcontentloaded")
    pg.fill("#quantity", "100")
    pg.wait_for_function("document.querySelector('#gauge svg') !== null")  # page script is running
    pg.click("button[type=submit]")
    pg.wait_for_timeout(300)
    assert "?" not in pg.url  # no form-submit navigation
    release[0].continue_()
    pg.click("button[type=submit]")
    pg.wait_for_function("document.querySelector('#co2-value').textContent === '170.0'")
    ctx.close()


def test_about_section_content(page, site_url):
    page.goto(site_url + "/index.html")
    about = page.inner_text("#about")
    for needed in ["Making Recycling Understandable. Making Everyday Actions Measurable.",
                   "initiative of VOiLA Sustainable Technologies Pvt. Ltd.",
                   "Foundation for Science, Innovation and Development (FSID)",
                   "Our Vision \u2014 From Awareness to Measurable Action",
                   "Our belief is simple:"]:
        assert needed in about, needed
    assert "non-profit" not in about
    # disclaimer is the last thing in the section, in small muted text
    assert page.evaluate("document.querySelector('#about > .wrap').lastElementChild.className") == "about-disclaimer"
    size = page.evaluate("parseFloat(getComputedStyle(document.querySelector('.about-disclaimer')).fontSize)")
    assert size < 14


def test_no_mention_of_former_lead(page, site_url):
    for path in ["/index.html", "/report.html#m=PET&q=100&u=kg&t=once&d=2026-11-06"]:
        page.goto(site_url + path)
        page.wait_for_timeout(300)
        assert "bose" not in page.content().lower(), path
