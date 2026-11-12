# nevo-diet

The cheapest diet that meets every Dutch nutrient norm, built from real products and real prices in Dutch supermarkets.
A linear program (Stigler's diet problem) on the Dutch food composition table NEVO 2025 and the prices of 10 chains
(Checkjebon), turned into a week of meals and a shopping list, with a local app to explore it.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

> **Not medical or dietary advice.** This is a mathematical model, built for curiosity. It covers healthy adults and not
> pregnancy, breastfeeding, children or medical conditions. Prices and matches can be wrong. See a dietitian or doctor before
> making real changes to your diet.

## Quick start

**1. Install.** You need Python 3.11 or newer.

```
git clone https://github.com/Frikandelli/nevo-diet
cd nevo-diet
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

On Windows the last two commands use `.venv\Scripts\`. With Nix or on NixOS, use `./app.sh` instead: it does all of this
(through `shell.nix`, a pinned nixpkgs), and the pip packages above do not run on NixOS as they are.

**2. Add the dataset.** The app opens at http://localhost:8501 and asks for it. The food data is free, but only RIVM may
hand it out, so it isn't in this repo:

- **[Request the NEVO dataset from RIVM](https://www.rivm.nl/en/dutch-food-composition-database/nevo-online-request-dataset)**:
  fill in your email and accept the conditions, and RIVM emails you a download link.
- Upload the zip in the app (or run `python3 setup_data.py path/to/the.zip`). That's all, and you only do this once per
  computer.

## The app

The **sidebar** on every page holds what to solve, in six numbered steps: who eats (profile), calories and protein
(with your body for the estimates), where you shop (chain), kind of plan (pure LP or a realistic week of meals, with a
Solve button), the cost per food, and which supplements the plan may use (set on the Supplements page); fruit, budget
and the ≥ 3 chains switch are folded under *Optional*. The pages:

| Page | What's there |
|---|---|
| **Plan** | The answer: €/day, the basket (pure) or the week's dinners, foods and shopping list (realistic), **My foods** (what you'll eat anyway), **Limits** (at most so much of a food or a whole kind; none by default), what that changes, and the nutrient check. ✗ a food or a whole kind (all pasta, all rice ...) right in the table, and put them back. Downloads: every table as CSV, the whole plan as a ZIP. |
| **Nutrients** | Charts of what's in the diet: minimums met, maximums used, which food gives which vitamin and mineral, where the energy and macros come from, where the money goes; the full nutrient table. |
| **Why this diet** | The LP explained through its dual: what each food is worth vs its price, what each food pays for (price split), what each limit costs (±10%), cost curves, wiggle room within 5%, what replaces what, the same diet at every chain. |
| **Foods** | All foods with prices and nutrients: ✗ to leave one out, whole kinds, a *cook* tick per food, allergy and category ticks. |
| **Supplements** | 28 vitamin and mineral pills, oils and psyllium with their cheapest price (supermarkets and drugstores), what each would save, and which ones the plan may use: only vitamin D by default, the ticked ones, every priced one, or all (no price = free ⚠). Your own prices and exact amounts. How each label is counted (folic acid ×1.7, B12 by dose ...). |
| **Dishes** | NEVO's dishes priced from their recipes at the chain, with ingredients and stand-ins. |
| **Profile & limits** | Your own profiles, and the minimum and maximum of every nutrient, each with its source. |
| **Data & sources** | Every dataset and what was done to it (`docs/data.md`), every table in `data/` and every report to download, the limits with their sources (`SOURCES.md`). |
| **How to use** | The sidebar step by step, what every setting does and when to change it, leaving foods out and putting them back, common tasks (`docs/how-to-use.md`). |
| **About** | What it is, how it works, where to find what, and the words it uses (`docs/about.md`). |
| **Settings** | Start over, reset the cook ticks, the solution cache (500 MB, least recently used out first), fetch new prices. |

Settings and exclusions are saved per computer in `~/.config/nevo-diet/settings.json`, own profiles in
`~/.config/nevo-diet/profiles.json`, solutions in `~/.cache/nevo-diet`: none of it in git. `python3 test_app.py` checks
that every page renders in many settings (about 5 minutes with a warm cache, longer the first time); it needs the
dataset.

## Where to find what

| Where | What |
|---|---|
| `app.py` | The app's entry point: the sidebar and the page list. |
| `views/` | One file per page of the app. |
| `ui.py` | What the pages share: the settings context, tables and charts with their downloads, the sources line, the ZIP export. |
| `charts.py` | Every chart (Altair), in one validated colour palette for light and dark mode. |
| `appcore.py` | Everything the app computes, as plain data, behind the disk cache. |
| `lp.py` | The model: foods, prices and nutrients in, the LP (and the cost-per-food MILP) out. |
| `supplements.py` | Supplements: labels → what the norms count (absorption rules), prices per shop, which ones the plan may use; run it to refresh their supermarket prices. |
| `profiles.py`, `cooking.py`, `categories.py`, `kinds.py` | Profile → limits; cooked or raw per food; the category and allergy ticks; kinds of food (wheat flour, pasta, rice ...). |
| `explain.py` | Duality: the price split, the removal tree, dropping one limit at a time. |
| `plan.py`, `meals.py`, `dishes.py` | Whole packs at one chain; a week of meals; NEVO dishes priced from their recipes. |
| `expand.py`, `catalog.py`, `amino.py`, `price.py`, `fetch_prices.py` | Building the data: products → NEVO foods → the catalog; amino acids; prices. |
| `run.py`, `compare.py`, `sensitivity.py` | The reports. |
| `data/` | The tables the model reads (see below). `data/nevo/`: the two NEVO files, put there by `setup_data.py` (not in git). |
| `docs/data.md` | Every dataset, its terms, and every step done to it. |
| `docs/how-to-use.md` | The app's How to use page: every setting, leaving foods out, common tasks. |
| `docs/about.md` | The app's About page: what it is, how it works, the glossary. |
| `SOURCES.md` | Where every limit comes from, how it was checked, where the model deliberately differs. |
| `reports/` | Where the scripts write their reports (below); not in git. |
| `FINDINGS.md` | What was learned along the way: data surprises, odd prices, matcher war stories. |
| `DESIGN.md` | How the model, plans, meals, supplements and app work, and why. |
| `setup_data.py` | Puts the two NEVO files in `data/nevo/` from RIVM's zip (the app does this on first start). |
| `NOTICE.md`, `LICENSE` | Data credits and their terms; the code is MIT licensed. |

## Data

Composition: NEVO 2025/9.0 (RIVM). Prices: Checkjebon, snapshot in `data/catalog_snapshot.txt`. Amino acids: USDA
FoodData Central SR Legacy. Cooking losses: NEVO's cooked entries, else the USDA Table of Nutrient Retention Factors
(Release 6). Limits: Voedingscentrum 2025, Gezondheidsraad, EFSA, WHO (`SOURCES.md`). **`docs/data.md` describes every
dataset and every manipulation**: matching, edible parts, drained weights, cooked or raw, absorbed iron, plant EPA/DHA,
amino acids, whole fruit, dish stand-ins.

Files you edit by hand (every change with a reason in the file):
- `data/foods.tsv`: the 53 hand-mapped staples (search pattern, NEVO raw and cooked code, edible fraction, yield).
- `data/review.tsv`: decisions on products: `exclude`, `remap:<NEVO code>` or `keep`.
- `data/requirements.tsv`: every limit: men's values, women's overrides, scaling per profile, source, link, evidence.
- `data/profiles.tsv`: the four standard profiles (average and active man and woman).
- `data/cooking.tsv`: which foods are cooked by default, and their USDA retention class.
- `data/supplements.tsv`: the supplements: label amounts per tablet, capsule or spoon, form, source and date.
- `data/supplement_prices.tsv`: who sells each supplement: shop, product, units per pack, price, source (Checkjebon or
  the shop's website) and date.
- `data/dinners.tsv`: which NEVO dishes count as dinners (quick or batch, hands-on minutes; the starch side column is no longer used).
- `data/kinds.tsv`: the kinds of food you can leave out at once (wheat flour, pasta and noodles, rice ...): rules on the
  food group and NEVO name, first match wins (`python3 kinds.py` lists every kind with its foods).

## Rebuild and reports

Optional: the catalog and the other derived tables are committed. `python3 fetch_prices.py` downloads the newest
Checkjebon snapshot (MIT), which the rebuild scripts need; the USDA SR Legacy CSV (public domain) goes in `data/usda/`,
only to rerun `amino.py`.

```
python3 expand.py [--sample 80]   # products -> NEVO matches: data/auto_matches.tsv, auto_prices.tsv (~1.5 min)
python3 catalog.py                # merged catalog: data/catalog_foods.tsv, catalog_prices.tsv, catalog_snapshot.txt
python3 supplements.py            # supermarket supplement prices from the newest snapshot: data/supplement_prices.tsv
python3 amino.py                  # amino acids per food: data/amino_foods.tsv (needs data/usda/)
python3 cooking.py retn06.txt     # USDA retention factors: data/retention.tsv
python3 run.py [--raw] [--profile avg_man]   # reports/<profile>.md: the full analysis per profile
python3 compare.py                # reports/profiles.md: the four profiles at every chain
python3 sensitivity.py            # reports/sensitivity.md: cooking and absorption scenarios
python3 plan.py [--chain ah]      # reports/plans.md: shopping lists in whole packs (~1 min)
python3 dishes.py [--chain ah]    # reports/dishes.md: NEVO dishes priced at every chain
python3 meals.py [--strictness medium]   # reports/meals.md: a week of meals (~1.5 min)
python3 profiles.py               # each profile's weight, energy and protein
python3 search.py nevo 'kool'     # find NEVO codes;  python3 search.py price 'kwark' finds products
```

## Modelling choices, in short

- Variables are grams as bought per day; prices are per 100 g of the edible part (peel, shell and bone off; tins drained).
- A blank NEVO cell counts as 0, which is cautious for minimums; the reports list the blanks that matter.
- Each food counts as it's usually eaten, cooked (boiled) or raw, with a *cook* tick per food in the app.
- Iron counts as absorbed iron (haem 25%, non-haem 10%); zinc uses EFSA's norm for a high-phytate diet.
- Plant foods have no EPA/DHA (NEVO's traces in oats and peanut butter are lab noise the optimiser exploited).
- Amino acids: USDA's profile per food family × NEVO protein × digestibility (0.95 animal, 0.85 plant), against WHO 2007.
- Supplements are pseudo-foods per tablet, counted as the norms count them (folic acid ×1.7, synthetic vitamin E ×0.67,
  B12 by dose, iron 10% absorbed); only the vitamin D tablet by default, the rest on the Supplements page. No caps of
  their own; magnesium from pills has EFSA's 250 mg maximum.
- No food has a limit of its own. Your own limits on a food or a kind are extra rows ("at most so many grams of these
  foods together"), counting dinner ingredients in the realistic week.
- Your own foods are bounds: at least the amount, or exactly it.
- Ignored: promotions, taste in the pure plan, absorption interactions within a meal, and phytate (NEVO has no data).
