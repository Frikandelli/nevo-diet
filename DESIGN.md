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
- **Cooking:** each food counts as it's usually eaten, boiled or raw, with a cook tick per food in the app. Cooked =
  NEVO's cooked entry × yield, otherwise the raw values × the USDA retention factors (Release 6). Cooking means boiling,
  the cautious choice.
- **Absorption:** the model counts absorbed iron (haem 25%, non-haem 10%) and uses EFSA's zinc for a high-phytate diet.
- **Amino acids:** all nine essential ones, from USDA profiles per food family × digestibility (0.95 animal, 0.85 plant), with
  WHO 2007 needs per kg. None bind.
- **Model rules:** plant EPA/DHA counts as 0, because NEVO lists traces from lab analyses and the LP built a vegetarian optimum
  on them. The NEVO data itself is never edited.
- **No limits on foods by default.** Only the nutrient limits and, in the realistic week, the meal rules restrain the
  LP, so expect odd plans (400 g of flour a day) unless you set your own limits on foods or kinds of food.
- **Supplements:** only a vitamin D tablet by default; the others are opt-in (see *Supplements* below).

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
- at least 250 g vegetables and 200 g fruit a day.

No rule caps a food any more (the 30%-of-energy rule and the starch-side rule went on 2026-11-09). Supplements come in
whole tablets a week.

## The app

`appcore.py` computes, `charts.py` draws (Altair), `app.py` holds the sidebar and the page list, and `views/` has one
file per page, with `ui.py` for what they share (Streamlit). Every result is a plain dict, cached as a
pickle keyed by settings and a hash of the data files and model code, with a least-recently-used limit of 500 MB. The pure LP
updates live; a realistic week runs on the Solve button. The *Why this diet* charts always use the pure LP, because duality,
removal, curves and ranges are LP concepts.

**Cheapest chain.** One real chain, unlike "all chains", which mixes chains per food. The pick follows the mode and the current
settings: pure ranks the LP at every chain, and realistic ranks a full week at all 10 chains, because packs and dinners differ
per chain. It's ranked on the price shown, so a cheaper week may bend more meal rules; "Every chain compared" shows the count.
The before-and-after stays at the picked chain, so it shows what your foods do, not a change of chain.

**My foods.** Foods from the catalog, in grams per day or week, exactly or at least, as bounds on the variables. They work in pure and
realistic mode, and in realistic they go on the shopping list in whole packs. A food the chain doesn't sell is priced at the
cheapest other chain and marked ⚠. An impossible amount gives no plan, but a message naming the limit in the way and the most
that still works. A before-and-after compares with the same plan without your foods, and a switch also takes away the ticks.
Your own food beats a tick or a ✗. "Exactly" counts what you eat as such; a dinner may use more on top. The removal tree never removes your own foods, and the
price split leaves them out, because the duality sum doesn't hold for a food on its lower bound.

**Category ticks** (`categories.py`). A tick removes everything containing that ingredient, including dinners, using NEVO's food
group, its English name and its recipes. Cooking basics (fats and oils, sugar, salt, yeast and the like) only stop being eaten as
such, and a dinner keeps its spoonful: taken strictly, "no fats and oils" would leave 3 of the 34 dinners. An average ("Beef av
raw") only takes on what at least half of the mix has. Borderline foods: peanuts and chestnuts are nuts, coconut isn't; goat's
milk and butter are dairy, plant drinks aren't; seed oils aren't seeds. **Allergy ticks** (gluten, lactose, milk, egg, fish,
shellfish, peanuts, tree nuts, soy, sesame) work the same way, and also read the real product names; when in doubt a food
goes out. NEVO has no allergen data, so they are no guarantee.

**Supplements** (`supplements.py`, `data/supplements.tsv`, `data/supplement_prices.tsv`). 28 vitamin and mineral pills,
multivitamins, fish and algae oil and psyllium, each a pseudo-food per tablet, capsule or spoon. Labels come from the
product pages, prices from the Checkjebon snapshot (supermarkets) or a drugstore's website (copied with the date). By
default the plan uses only a 25 µg vitamin D tablet; on the Supplements page you tick others, allow every one with a
price, or every one (a supplement without a price then counts as free, and the price says so with a ⚠). Pills are bought
at the cheapest shop by default, drugstores included, because they keep for a year; your own prices and exact amounts
(per day or per week) are saved on your computer. A label is converted to what the norms count: folic acid ×1.7 as folate
(EFSA's dietary folate equivalents), synthetic vitamin E ×0.67 (IOM 2000), B12 by dose (about 1.2 µg per dose taken up
actively plus 1% passively, so 1000 µg counts as 22 µg), iron as non-haem iron (10% absorbed), the rest as on the label.
Magnesium from pills gets EFSA's upper limit of 250 mg a day, which is for supplements only. No supplement has a cap of
its own; the nutrient maximums bound them. The realistic week takes them in whole tablets a week. The fish oil follows
the "no fish" tick, and a gelatin capsule the "no meat" tick. A "saves €/day" column re-solves the plain LP with each
supplement switched on or off.

**Kinds and limits** (`kinds.py`, `data/kinds.tsv`). Every food has one kind (wheat flour, pasta and noodles, rice, oily
fish ...), from its food group and NEVO name, so a whole kind can be left out at once, which is a ✗ on each of its foods.
Your own limits ("at most so many grams a day or a week of a food, or of all foods of a kind together") are extra rows in
the LP, not bounds on a variable: so they work the same in pure and realistic mode, count a food in dinners too (from
the recipe), and have a shadow price like any nutrient limit.

**Cook ticks.** Each food has a tick: ticked counts it cooked, unticked raw. Defaults follow how the food is usually eaten
in a Dutch kitchen; a must-cook food set to raw is allowed, with a warning. Ticks, like the ✗ marks, wait for an Apply
button, so a quick series of clicks isn't lost.

**Cost per food.** An optional charge (€0.05 a day recommended) for every food in the plan, so a food only comes in if it
saves at least that much. The MILP only picks the foods; the LP is then solved again on those foods, so the price shown
is the real one without the charge, and duality still holds for the basket.


## Rules for the data

- Never commit the NEVO files, and never change NEVO values. Handle suspicious values with documented model rules in code.
- Every output carries "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources".
- Never invent nutrient or requirement numbers. Take them from a published source, and record it in `data/requirements.tsv`.
