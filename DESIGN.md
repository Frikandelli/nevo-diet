# Design

How the model, plans, meals and app work, and why. Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and
other data sources. Limits and their evidence are in `SOURCES.md`.

## The model

Minimise cost subject to nutrient bounds: a linear program over grams per day of each food (Stigler's diet problem), solved
with HiGHS. About 610 foods: 50 hand-mapped (`data/foods.tsv`) and the rest auto-matched by `expand.py`, priced per chain.

- **Foods:** basic foods only, with a known weight or volume. Composite products are skipped, since the model combines basic
  foods itself. Matches are checked by confidence, and decisions on products are recorded in `data/review.tsv`.
- **Availability:** a food sold at fewer than 3 of the 10 chains counts as hard to get. Anything not sold at the chosen chain
  is out.
- **Composition:** cooked ("as eaten") by default, with a raw switch.
- **Absorption:** the model counts absorbed iron (haem 25%, non-haem 10%) and uses EFSA's zinc for a high-phytate diet.
- **Amino acids:** all nine essential ones, from USDA profiles per food family × digestibility (0.95 animal, 0.85 plant), with
  WHO 2007 needs per kg. None bind.
- **Model rules:** plant EPA/DHA counts as 0, because NEVO lists traces from lab analyses and the LP built a vegetarian optimum
  on them. A vitamin D tablet is a priced pseudo-food, at most 1 a day. The NEVO data itself is never edited.
- **No daily caps per food.** Only nutrient limits and, in the realistic week, the meal rules restrain the LP.

The LP exploits every missing constraint and every data error. When a strange food enters a basket, check the product and its
NEVO values before trusting the result.

## Profiles

Standard profiles in `data/profiles.tsv`: an average and an active man and woman. Requirements follow from the profile: energy
from resting energy × activity level, protein per kg, fibre and some B vitamins per MJ, amino acids per kg, and sex-specific
norms.

Weight, height and targets can be changed in the app, and own profiles and limits are saved in
`~/.config/nevo-diet/profiles.json`. The scripts and reports only use `data/`, so they stay reproducible. Calories without a
target use Henry 2005 when a height is known, otherwise Schofield 1985. No pregnancy or breastfeeding profiles.

## Explanations

- **Price split:** at the optimum a food's price equals Σ shadow price × nutrient content over the binding requirements
  (LP duality), which shows what each food is really bought for.
- **Removal tree:** remove the biggest food, re-solve, see what replaces it, a few levels deep.
- **Cost curves and wiggle room:** cost as one requirement is pushed up, and each food's range within 5% of the cheapest cost.

## Shopping plans (`plan.py`)

A MILP with whole packs at one chain, as a repeating weekly list and a 4-week rotation.

- Pantry foods (dry goods, cans, oil, nuts, frozen, tablets) are paid per gram used. Fresh foods have a shelf life in weeks.
- A freezer holds at most 10 kg between weeks.
- Most nutrients hold over the week. Vitamins A, D, B12 and K1, iron, iodine, selenium and EPA/DHA hold over 4 weeks. Upper
  limits always hold per week.

## A week of meals (`meals.py`, `dishes.py`)

Dinners are NEVO dishes (`data/dinners.tsv`: 34 dishes, marked quick or batch), priced from their ingredients. A dish's nutrients
are NEVO's own values for the dish. Two patterns: brunch + warm dinner + snacks with leftovers, or classic breakfast, lunch and
dinner.

Rules are soft, with one strictness setting. A rule may only be bent if that saves at least €0.25/day (medium) or €0.10/day
(loose), and every bent rule is reported with its saving. Strict bends none.

- at least 4 different dinners a week, none more than twice;
- at least 2 bread toppings a week;
- at least 250 g vegetables and 200 g fruit a day;
- no food above 30% of energy.

## The app

`appcore.py` computes, `charts.py` draws (Altair) and `app.py` is the UI (Streamlit). Every result is a plain dict, cached as a
pickle keyed by settings and a hash of the data files and model code, with a least-recently-used limit of 500 MB. The pure LP
updates live; a realistic week runs on the Solve button. Charts 3, 5, 6 and 7 always use the pure LP, because duality, removal,
curves and ranges are LP concepts.

## Rules for the data

- Never commit the NEVO files, and never change NEVO values. Handle suspicious values with documented model rules in code.
- Every output carries "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources".
- Never invent nutrient or requirement numbers. Take them from a published source, and record it in `data/requirements.tsv`.
