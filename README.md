# nevo-diet

What's the cheapest diet that meets every Dutch nutrient norm, using real products and prices from Dutch supermarkets?
This is a linear program (Stigler's diet problem) on the Dutch food composition table, with a local app to explore it:
weekly shopping lists, a week of meals, your own body and goals, and charts showing why each food is in the basket.

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

On Windows the last two commands use `.venv\Scripts\`. With Nix or on NixOS, use `./app.sh` instead: it does all of this, and the pip packages above do not run on NixOS as they are.

**2. Add the dataset.** The app opens at http://localhost:8501 and asks for it. The food data is free, but only RIVM may
hand it out, so it isn't in this repo:

- **[Request the NEVO dataset from RIVM](https://www.rivm.nl/en/dutch-food-composition-database/nevo-online-request-dataset)**:
  fill in your email and accept the conditions, and RIVM emails you a download link.
- Upload the zip in the app. That's all, and you only do this once per computer.

Your profiles and settings stay on your computer, in `~/.config/nevo-diet/`.

## The app

- **Plan:** the cheapest diet, as a bare linear program or as a realistic week of meals in whole packs.
- **Chain:** pick a supermarket, mix all chains (pure mode only), or choose "cheapest chain" and let the app find the one chain with
  the lowest price under your settings. In realistic mode that compares a full week at every chain, about a minute on Solve.
- **My foods:** on the Plan tab, pick foods you'll eat anyway, with grams per day or week, exactly or at least. The plan fills in
  the rest, and shows what your foods changed.
- **Category ticks:** on the Foods tab, no meat, no nuts, no grain products and so on. These are preferences, **not allergy protection**.
- **Foods:** every food with its prices and nutrients. Exclude any food with one click.
- **Dishes:** NEVO's dishes, priced from their ingredients.
- **Charts:** nutrient coverage, which food covers which micronutrient, where the money goes, what each food pays for
  (LP duality), what replaces what, cost curves and wiggle room.
- **Profile & limits:** create or edit profiles, and set the minimum and maximum per nutrient. Every limit shows its source.
- **Settings:** cache size, and fetching new prices.

At the top you can change weight, height and the calories and protein targets for the selected profile.

## How it's built

- `SOURCES.md`: where every limit comes from, what was checked, and where the model deliberately differs.
- `DESIGN.md`: how the model, plans, meals and app work, and why.
- `FINDINGS.md`: what was learned along the way: data surprises, price oddities, matcher war stories.
- `NOTICE.md`: data credits and licences. The code is MIT licensed (`LICENSE`).

`python3 test_app.py` checks that every tab renders. It needs the dataset.

## Rebuilding the data and reports

These scripts are optional; the catalog is committed. `python3 fetch_prices.py` downloads the latest Checkjebon snapshot
(MIT licensed), which the rebuild scripts need. Amino acids: USDA FoodData Central SR Legacy CSV (public domain) unzipped into
`data/usda/`, only to rerun `amino.py`.

```
python3 expand.py [--sample 80]   # auto-match all products to NEVO -> data/auto_matches.tsv, auto_prices.tsv
python3 catalog.py                # merge with the hand-mapped foods -> data/catalog_foods.tsv, catalog_prices.tsv
python3 amino.py                  # USDA amino acid profiles per food -> data/amino_foods.tsv
python3 run.py [--raw] [--profile avg_man]   # analyses per profile -> reports/<profile>.md
python3 compare.py                # all profiles x chains -> profiles.md
# each report also explains the basket (explain.py): chains per food, price split, removal tree, rule costs
python3 profiles.py               # print each profile's weight, energy and protein
python3 plan.py [--chain ah]      # shopping lists in whole packs at one chain -> plans.md
python3 dishes.py [--chain ah]    # NEVO dishes priced from their ingredients -> dishes.md
python3 meals.py [--strictness medium]   # a week of meals -> meals.md
python3 sensitivity.py            # cooking losses + absorption scenarios -> sensitivity.md
python3 search.py nevo 'kool'     # find NEVO codes;  python3 search.py price 'kwark' finds products
python3 price.py                  # (old) price only the 50 hand-mapped foods -> data/prices.tsv
```

## Files you edit
- `data/dinners.tsv`: which NEVO dishes count as dinners (quick/batch, hands-on minutes, starch side).
- `data/review.tsv`: hand decisions on products: `exclude` a product, or `remap:<NEVO code>` it.
- `data/foods.tsv`: one row per food: NEVO code (raw and as-eaten), price regex + exclusions, edible fraction,
  piece weight, cooking yield (`P` = estimated from protein, raw/cooked).
- `data/profiles.tsv`: the standard profiles (average and active man and woman).
- `data/requirements.tsv`: Dutch norms (Voedingscentrum 2025 table of Gezondheidsraad values, EFSA zinc, WHO amino
  acids; sources per row): men's values, women's overrides, and how each scales with the profile.

## Modelling choices
- Variables are grams as bought per day; prices are per 100 g edible portion (peel/shell/bone removed).
- A blank NEVO cell counts as 0, which is conservative for minimum requirements. `run.py` lists blanks in nutrients
  that bind.
- EPA/DHA counts as 0 for plant foods. This is a model rule, not a change to the NEVO files: NEVO lists trace
  "DHA" in oats and peanut butter from lab analyses, and the LP built the vegetarian optimum on it.
- A vitamin D tablet (AH Care D3 25 µg, €4.99 for 300) is included as a priced pseudo-food, at most 1 a day.
- Cooked mode (the default; `python3 run.py --raw` for raw values) swaps in NEVO's as-eaten entry × yield. For boiled vegetables the yield is
  assumed to be 1.0.
- Your own foods are bounds on the variables: x >= amount, and x <= amount as well when it's "exactly". They count
  in grams as bought and stay in whatever a tick, a ✗ or the chain says about them.
- Absorption: NEVO is not corrected for bioavailability (background doc §4.4). The model counts absorbed iron
  (haem 25%, non-haem 10%; target = norm x EFSA absorption) and uses EFSA's zinc for a high-phytate diet. `sensitivity.py`
  varies these assumptions and calcium from soy drink.
- Amino acids: USDA mg per g protein for the food's family (oats, wheat, legumes, dairy, ...) x NEVO protein x
  digestibility (0.95 animal, 0.85 plant); NEVO's own tryptophan where it has one. Needs: WHO 2007 per kg.

## Ignores
Promotions, taste, meal-level
absorption interactions (vitamin C with iron, calcium against iron), and phytate (NEVO has no phytate data).
