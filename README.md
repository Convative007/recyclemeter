# RecycleMeter

RecycleMeter is a plastic recycling impact calculator. You enter a plastic type and the weight recycled. It estimates the greenhouse gas emissions avoided by not producing the same amount of virgin plastic, and shows them as everyday equivalents: trees, litres of petrol and smartphone charges.

RecycleMeter is a free, non-commercial sustainability education and awareness initiative.

Live site: <https://recyclemeter.org>

It is a static front end (HTML, CSS, JavaScript) with no backend. Python is used to build it, serve it locally and test it.

## What it does

| Area | Detail |
| --- | --- |
| Inputs | Plastic type dropdown (PET, HDPE / LDPE, PP, Mixed plastics) with a "Mechanical Recycling Baseline" badge and tooltip; weight with a kg / lbs toggle; one-time or monthly |
| Result | Total CO2 prevented, shown on a gauge (kg, switching to tonnes above 1,000 kg); for monthly input, an annual total (x 12) |
| Equivalents | Trees planted, litres of petrol not burned, smartphone charges powered |
| Breakdown | For PET, PE and PP, a virgin-versus-recycled emissions comparison |
| How It Works | Formula, emission factor table, equivalency constants; a "Methodology & Science" accordion that opens with the "System Scope & Recycling Methodology" callout, then the assumptions |
| Results footnote | Mechanical-recycling note under the equivalents and the virgin-versus-recycled chart |
| Impact Reports | Printable report with a reference number and date; print or save as PDF; download data (JSON) |
| About | Initiative description, vision and disclaimer |
| Contact | "Email us at impact@recyclemeter.org" |
| Footer | "Methodology & Sources" with six academic and industry references |

## Calculation

```
CO2 saved (kg) = weight recycled (kg) x (EF_virgin - EF_recycled)
```

| Plastic | EF virgin | EF recycled | Saved per kg |
| --- | --- | --- | --- |
| PET | 2.8 | 1.1 | **1.7** |
| HDPE / LDPE | 1.8 | 0.7 | **1.1** |
| PP | 1.9 | 0.8 | **1.1** |
| Mixed plastics | n/a | n/a | **1.3** |

Units are kg CO2e per kg. Pounds are converted at 1 lb = 0.453592 kg.

| Equivalent | Calculation |
| --- | --- |
| Trees planted | CO2 / 21.7 (kg a mature tree absorbs in a year) |
| Litres of petrol | CO2 / 2.3 |
| Smartphone charges | CO2 x 121 |

Worked example: 100 kg of PET gives 170 kg CO2e prevented, 7.83 trees, 73.9 litres of petrol and 20,570 smartphone charges.

All factors and constants live in one versioned file, [`data/factors.json`](data/factors.json). The page reads them from there and never takes them from user input.

## Getting started

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # Jinja2
python manage.py serve               # builds dist/ and serves http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000>. The server rebuilds when files change.

**On your phone (same Wi-Fi):**

```bash
caffeinate -i python manage.py serve --host 0.0.0.0
```

Then open `http://<your-mac's-ip>:8000` on the phone. Run `ipconfig getifaddr en0` to find the IP. `caffeinate` stops the Mac sleeping while the server runs. Press Ctrl+C to stop.

The site must be served over HTTP. It doesn't work when the HTML file is opened directly, because it loads the factor file.

| Command | Does |
| --- | --- |
| `python manage.py build` | Render the static site into `dist/` |
| `python manage.py serve [--host H] [--port N] [--no-watch]` | Build and serve |
| `python manage.py test` | Run the tests |

## Tests

```bash
pip install -r requirements-dev.txt
playwright install chromium          # once
python manage.py test
```

There are 56 tests:

- **Factors and constants:** the published multipliers and equivalency constants; virgin minus recycled equals the multiplier; the pound conversion.
- **Calculation:** expected values computed independently from the formula (`tests/vectors.json`), checked against both the Python and the in-browser JavaScript engine; the monthly x 12 annual figure.
- **Validation:** zero, negative, blank and non-numeric weights are rejected.
- **Report:** it shows the same numbers as the screen, its download carries the factor-set version, and its "back" link restores the calculation.
- **Content:** the required text is present.
- **Mechanical-recycling scope:** the callout opens the accordion; the badge tooltip works by hover, tap and Escape and stays on-screen at 360, 390 and 1280 px; the footnote is last in the calculator section; the email sits in Contact.
- **Layout and accessibility:** no horizontal scrolling at phone width; a WCAG 2.1 AA audit (axe-core) passes in light and dark themes.

## Project layout

```
manage.py                 build / serve / test
data/factors.json         emission factors and equivalency constants (single source of truth)
data/site.json            name, tagline, scientific lead
src/recyclemeter/         engine.py (Python reference engine), build.py, server.py
templates/                index.html (single page), report.html, 404, icons and logo
static/css/main.css       design system (light and dark)
static/js/                engine.js (pure calculation), calculator.js, report.js
tests/                    pytest suite and vectors.json
dist/                     generated output (git-ignored)
```

## Design

- **Look:** green and white, card-based, subtle shadows. The signature element is a gauge, the "meter", on a logarithmic scale from 1 kg to 100 tonnes.
- **Self-contained:** custom line icons, system fonts, no external scripts, fonts or trackers.
- **Themes:** light and dark modes follow the device setting.
- **Phone:** a menu button replaces the link row.

## Deployment

Every push to `main` builds the site and publishes it to GitHub Pages (`.github/workflows/pages.yml`), served at the custom domain recyclemeter.org. DNS is at GoDaddy: four `A` records for `@` (185.199.108–111.153) and a `www` CNAME to `convative007.github.io`.

`dist/` is plain static files with relative links, so it can also be hosted on Netlify, Vercel or any static host.
