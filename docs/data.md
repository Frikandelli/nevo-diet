# The data, and what is done to it

Everything the app and the reports compute comes from the datasets below. **No source file is edited.** Where a value
looks wrong, or the model needs a number the data doesn't have, a documented *model rule* in the code says how the
value is used; this page lists them all. The same text is the first tab of the app's **Data & sources** page, which
also has every derived table to download.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

## The datasets

| Dataset | Version | From | Terms | What it gives the model |
|---|---|---|---|---|
| **NEVO-online** (Dutch food composition table) | 2025/9.0 | RIVM | Free to use with the reference line above; values unchanged; not for sale | Nutrients per 100 g edible part for 2,328 foods (148 columns), and 695 recipes (how a dish is made from other NEVO foods) |
| **Checkjebon** (supermarket products) | snapshot of 2026-10-30 | github.com/supermarkt/checkjebon | MIT | 107,271 products at 10 chains: name, pack size, price |
| **USDA FoodData Central, SR Legacy** | April 2018 | USDA Agricultural Research Service | Public domain | Essential amino acids per gram of protein (NEVO only has tryptophan) |
| **USDA Table of Nutrient Retention Factors** | Release 6, 2007 | USDA Agricultural Research Service | Public domain | The share of each vitamin and mineral left after boiling, for foods NEVO has no cooked entry for |
| **Nutrient norms** | Voedingscentrum 2025; Gezondheidsraad 2015/24, 2021/10, 2022/19, 2025/19, 2026/14; EFSA; WHO | see `SOURCES.md` | Cited per limit | Every minimum and maximum, with a link per row in `data/requirements.tsv` |
| **Body heights** | CBS StatLine 81565NED, 2025 | CBS | CC BY 4.0 | The average heights of 30-40 year olds, for the standard profiles |
| **Energy equations** | Henry 2005; Schofield 1985 | via Gezondheidsraad 2022/19 | Cited | Resting energy from weight (and height), times the activity level |
| **Supplements** | labels and drugstore prices of 2026-11-09; supermarket prices from the snapshot | product pages of PLUS, De Online Drogist, Vitaminstore; Checkjebon | Copied by hand, with the source per row | 28 vitamin and mineral pills, oils and psyllium the plan may use, as counted by the norms (see Supplements below). By default only the vitamin D 25 µg tablet |

The NEVO files aren't in this repository: RIVM's terms don't allow redistributing them. Request the dataset from
RIVM (rivm.nl → NEVO online → request dataset); the app asks for the zip on first start, or run
`python3 setup_data.py path/to/the.zip`. It puts the two files the code reads in `data/nevo/`, unchanged. The Checkjebon snapshot and the
USDA files aren't in git either: `fetch_prices.py` downloads the newest snapshot, and the USDA files are only needed to
rebuild the derived tables, which are committed.

## From products to foods

1. **Matching** (`expand.py`). Every product whose label gives a weight or volume is matched by its Dutch name to one
   *basic* NEVO food (vegetables, dairy, grain, meat, ...). Composite products (ready meals, sauces, snacks, "X met Y")
   are skipped: the model combines basic foods itself. A product whose match is ambiguous is dropped. 30,108 products
   (28%) have no usable weight ("per stuk"), so most loose fruit and eggs sold per piece can't be priced. About 90% of
   the matches are right; the cheapest-per-chain choice hides most of the wrong ones, and every product that ends up in
   a plan was checked by hand. → `data/auto_matches.tsv` (every match), `data/auto_prices.tsv` (cheapest per food and chain)
2. **Hand decisions** (`data/review.tsv`). A product can be excluded, remapped to another NEVO code, or kept after a
   check, always with the reason. Examples: fruit yoghurt and a banana houseplant matched as fruit are out;
   Dutch sun-dried tomatoes are remapped to NEVO's "in oil" entry.
3. **Hand-mapped foods** (`data/foods.tsv`). 53 staples with their own search pattern, NEVO code, cooked partner, yield
   and edible fraction. They win when the matcher finds the same NEVO food.
4. **The catalog** (`catalog.py`). Hand and automatic foods merged: 608 foods, each with the cheapest product at every
   chain that sells it. → `data/catalog_foods.tsv`, `data/catalog_prices.tsv`, and `data/catalog_snapshot.txt` (which
   snapshot it was built from).

## Prices

- **Per 100 g of the edible part,** like NEVO: the pack price divided by the edible grams. Peel, cores, shells and bones
  are taken off (bananas lose 36%, oranges 27%, apples 10%, eggs 12%), so bananas at €1.93/kg on the shelf are
  €3.02/kg of banana eaten. Shellfish have their own edible fraction (mussels 20%).
- **Tins and jars:** NEVO's canned vegetables, pulses and fish are per 100 g *drained*, so a can counts as 60% food.
- **Oil:** priced per kg (1 litre ≈ 0.92 kg).
- **The cheapest product per food and chain** is the food's price there. "Every chain" in the app takes each food from the
  chain that sells it cheapest; a plan at one chain uses only that chain's prices.
- **Promotions** are whatever the snapshot shows that day; nothing is corrected for them.

## Nutrients: how NEVO's values are used

- **A blank NEVO cell counts as 0.** About 23% of the micronutrient cells are blank (unknown). Counting them as 0 is
  cautious for minimums, but bread, for example, then has "no" vitamin K1. The reports list the blanks in foods that
  matter.
- **Cooked or raw** (`cooking.py`, rules in `data/cooking.tsv`). Each food is counted as it's usually eaten: cooked for
  raw meat, fish, eggs, frozen vegetables, dried pulses, flour, pasta, rice and potatoes, and for vegetables usually
  cooked in a Dutch kitchen; raw for tomatoes, peppers and oat flakes; as sold for tinned, smoked or ready-to-eat foods.
  *Cooked* means boiled:
  - where NEVO has a cooked entry for the food, its values × the yield (grams cooked per gram raw, from the recipe or
    estimated from the protein content), so amounts stay in grams as bought;
  - otherwise the raw values × the USDA retention factor per nutrient (`data/retention.tsv`); nutrients USDA gives no
    factor for (protein, fat, fibre, vitamins D, E and K) stay at 100%;
  - vegetables have a yield of 1.0: NEVO's raw and cooked vegetables come from different samples, so the protein trick
    gives nonsense there (white cabbage would "grow" 2.2×).
  - In the app every food has a *cook* tick to change this.
- **Absorbed iron.** NEVO gives total iron and haem iron. The model counts what the body absorbs: 25% of haem iron and
  10% of the rest, against the norm × EFSA's absorption (men 11 mg × 16% = 1.76 mg; women 18-49 16 mg × 18% = 2.88 mg).
  A blank haem cell counts all iron as non-haem.
- **Zinc** uses EFSA's norm for a diet high in phytate (men 14.0 mg, women 11.0 mg), because a cheap diet is mostly
  grains and pulses. NEVO has no phytate data.
- **No EPA or DHA from plants.** NEVO lists traces of DHA in oats and peanut butter (lab values near the detection
  limit); plants can't make it, and the optimiser built a vegetarian diet on those traces. Plant foods count as 0.
- **Essential amino acids** (`amino.py`). NEVO only has tryptophan. Each food gets the median USDA amino acid profile of
  its family (oats, wheat, rice, legumes, soy, dairy, meat, fish, ...) in mg per gram of protein, times NEVO's protein,
  times a digestibility of 0.95 (animal) or 0.85 (plant). NEVO's own tryptophan is used where it has a value.
- **Whole fruit,** for the fruit minimum: NEVO's fruit group minus dried fruit, prunes, olives, lemon, lime, coconut,
  juice, jam, syrup, fruit snacks and sweetened apple sauce.
- **Dishes** (`dishes.py`): a NEVO dish counts only if every ingredient of its recipe has a price at the chain (water,
  herbs and spices are free). The dish's nutrients are NEVO's own values for the dish; the ingredients only give the
  price and the shopping list. Ingredients sold per piece or not at all are priced through a stand-in from the same
  food family, and the Dishes page names every stand-in.
- **Categories and allergies** (`categories.py`): worked out from NEVO's food group, the food's name and its recipe, and
  for allergies also from the real product names. When in doubt a food goes out. It is not allergen data, and not a
  guarantee.
- **Kinds of food** (`kinds.py`, rules in `data/kinds.tsv`): every food belongs to one kind (wheat flour, pasta and
  noodles, rice, oily fish, cabbages ...), from its food group and NEVO name, so a whole kind can be left out, or
  limited, at once. Only a grouping for the app's ticks and limits: no nutrient value depends on it.

## Supplements

`supplements.py`, `data/supplements.tsv` (what is in each one), `data/supplement_prices.tsv` (who sells it, for how much).

- **The list:** 28 supplements: vitamin D (10, 25, 50, 75 µg), B12 (100, 1000 µg), vitamin C (70, 1000 mg), folic acid
  and methylfolate, a B-complex, three multivitamins, calcium + magnesium + zinc, calcium + D, magnesium (oxide and
  citrate), iron, zinc + copper, selenium, iodine (kelp), potassium, vitamin E, fish oil, two algae oils and psyllium.
  Each is one composition; several products can sell it (the 25 µg vitamin D tablet comes from AH Care, PLUS,
  Unipharma, Lucovitaal and Vitakruid).
- **Labels:** copied from the product page (PLUS, De Online Drogist, Vitaminstore), or, for a single vitamin or mineral,
  the dose in the product's name. Every row has its source and date. A label that gives the dose for 2 tablets is halved
  per tablet. Albert Heijn's product pages can't be read by a script, so AH's own multivitamins (Care) aren't in the list;
  Lidl's pills have no pack size in the Checkjebon data; no protein powder had a label that could be checked.
- **Prices:** supermarket products from the Checkjebon snapshot (55 products in all; refreshed with the food prices);
  drugstore products (iron, zinc, selenium, iodine, potassium, vitamin E, algae oil) copied by hand from De Online
  Drogist and Vitaminstore on 2026-11-09, which don't refresh. The price per unit is the pack price ÷ the units in it.
  With *buy at any shop* (the default) a supplement costs what its cheapest product costs anywhere; otherwise only your
  chain counts, and a supplement your chain doesn't sell has no price. A price you type on the Supplements page replaces
  the shop's, and is saved on your computer only.
- **No price = free.** With "every supplement" a supplement without a price costs €0 in the plan, and the Plan page says
  so with a ⚠.
- **Which ones the plan may use:** only the vitamin D 25 µg tablet by default (as before), the ones you tick, every one
  with a price, or every one. An exact amount (per day or per week) fixes it. No supplement has a cap of its own; the
  nutrient maximums bound them, as for food. The realistic week takes them in whole tablets a week.
- **How a label is counted** (model rules). The norms assume food, so a pill is converted to what it is worth as food:
  - *folic acid* ×1.7 as folate, the dietary folate equivalents of
    [EFSA 2014](https://www.efsa.europa.eu/en/efsajournal/pub/3893); methylfolate the same
    ([EFSA 2022](https://www.efsa.europa.eu/en/efsajournal/pub/7452)). It also counts against the folic acid maximum.
  - *vitamin E:* natural (d-alpha) ×1, synthetic (dl-alpha) ×0.67. The label's mg alpha-TE count the synthetic form at
    74% of natural; the norms count only the natural-shaped half (IOM 2000: 0.45 mg alpha-tocopherol per mg of the
    synthetic acetate, against 0.67 on the old scale; EFSA 2015 follows it).
  - *vitamin B12* by dose: absorbed = the smaller of half the dose and 1.2 µg (what intrinsic factor takes up per dose),
    plus 1% of the dose (passive diffusion), counted as the food B12 absorbed as much (÷ 0.5). 25 µg counts as 2.9 µg,
    100 µg as 4.4 µg, 1000 µg as 22.4 µg. From the [St John's study of B12 absorption by
    dose](https://www.stjohns.in/publications/the-oral-bioavailability-of-vitamin-b12-at-different-doses-in-healthy-indian-adults)
    (about 50% of 2.5 µg, active uptake levelling off near 1.2 µg) and the
    [Cochrane review of oral B12](https://pmc.ncbi.nlm.nih.gov/articles/PMC5112015) (about 1% of a large dose).
  - *iron* as non-haem iron: 10% absorbed, like the iron in plants.
  - *vitamin A:* every product here has retinol (retinyl acetate): ×1, and against the retinol maximum.
  - *magnesium from pills* has its own maximum of 250 mg a day: EFSA's upper limit is for supplements only (food
    magnesium has none). A row added to the program when a pill with magnesium is in it.
  - *everything else* ×1: no Dutch or EFSA norm gives a factor for pills. Magnesium oxide is said to be absorbed worse
    than citrate, but there is no agreed number, so the page only shows the form. The ~9 kcal of oil in a capsule is
    left out; a fizzy multivitamin's sodium isn't on its label and isn't counted.

## Limits and profiles

- **No limits on foods by default.** No food, kind or supplement has a maximum of its own (magnesium from pills has a
  nutrient maximum, see Supplements); the plan may use any food in
  any amount the nutrient limits allow. (Until 2026-11-02 there were daily caps per food group; until 2026-11-09 the
  vitamin D tablet was capped at 1 a day, and the realistic week had three rules of its own: no food above 30% of the
  energy, pasta, rice and potatoes only as a 150 g side with a dinner that takes one, and no raw flour, sugar, tomato
  paste, starch or bakery mixes eaten as such. All gone.)
- **Your own limits on foods** (Plan page → *Limits*): *at most* so many grams a day or a week of a food, or of all the
  foods of a kind together, as bought. Each is one more row in the linear program, next to the nutrient rows, so it
  counts a food in dinners too (the dish's ingredients from its NEVO recipe) and has a shadow price like any limit.

- `data/requirements.tsv` holds every limit once, for men, with women's values where they differ, and how it scales:
  energy with the profile's calories (a band of +4%), protein per kg, fibre, thiamin and niacin per MJ, amino acids per
  kg. Every row has its source, a link and how firm the evidence is. `SOURCES.md` says how each was checked and which
  ones newer advice has changed.
- `data/profiles.tsv` has the four standard profiles: average and active man and woman, 35 years old, at a healthy
  weight (BMI 22) for the average Dutch height. Your own profiles and limits are saved on your computer only
  (`~/.config/nevo-diet/profiles.json`).

## What the model doesn't know

Taste, promotions, how foods combine in the gut (vitamin C helping iron, calcium hindering it), phytate, foods sold
per piece without a weight, and products a chain sells in shops but not online. About 10% of the automatic matches
are wrong. The app is a calculation, not dietary or medical advice.
