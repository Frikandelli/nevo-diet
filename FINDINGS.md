# Findings

Things learned while building this that don't show up in the app: surprises in the data, odd supermarket
prices, matcher war stories, and what the optimiser does when you let it. Newest stage at the bottom. Numbers are from when
each stage was built, so later changes to the foods, caps and limits have moved some of them. "High-protein profile" means
1.6 g/kg at 2,950 kcal, an example used during the build.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources (Checkjebon price
snapshot of 2026-10-30, Voedingscentrum 2025 norms).

---

## The food table (NEVO 2025/9.0)

- **2,328 foods × 148 columns, all per 100 g of the *edible* part.** Values use decimal commas and `|` as the
  separator. Read them naively and `1,8` becomes text or 18.
- **About 23% of the micronutrient cells are blank** (unknown, not zero). The model counts a blank as 0. That's
  conservative for minimum requirements, but means e.g. bread has "no" vitamin K1.
- **Vitamin K is split into K1 and K2**, and the Dutch norm (70 µg) is for **K1 specifically**. Aged Gouda has
  65 µg K2 per 100 g; kale has 817 µg K1.
- **Tryptophan is the only amino acid in NEVO.** Lysine, methionine etc. need another source (stage 2).
- **There's a free-sugars column** (`NVSUGAF`, "vrije suikers"), which makes the WHO limit (< 10% of energy)
  possible. Chocolate milk: 10.5 g total sugar, of which 6 g free.
- **NEVO is *not* corrected for absorption**, except through the equivalents it already uses: vitamin A as RAE,
  folate as DFE, niacin equivalents and vitamin E. It does split iron into haem and non-haem.
- **Canned vegetables, legumes and fish are per 100 g *drained*.** A 400 g can holds about 240 g of beans, so
  pricing on net weight underestimates the price by ~40%. The first version of this model did exactly that.
- **"DHA" in oats (0.04 g) and peanut butter (0.10 g).** These are real lab values from 2024 Eurofins and 2015
  TNO analyses, but plants can't make DHA: it's almost certainly a misidentified chromatography peak near the
  detection limit. 27 plant foods have this. **The LP built the cheapest vegetarian diet around it**, until
  plant EPA/DHA was set to 0.
- **Raw and cooked entries come from different samples**, so for vegetables the difference isn't purely a
  cooking effect. Boiled broccoli has *more* potassium (399 mg) than raw (227 mg), and the protein-ratio trick
  gives white cabbage a "cooking yield" of 2.2. For grains and legumes it works fine: pasta 2.4×, lentils
  2.4×, split peas 2.6×, as in a real kitchen.
- **Cooking costs vitamin C:** red cabbage 60 → 38 mg/100 g, white cabbage 29 → 15, spinach 15 → 8.
  Switching the model to "as eaten" makes the cheapest diet €0.08/day more expensive, and red cabbage more
  than doubles to make up for it.
- **Bread carries Dutch iodine:** 61 µg per 100 g of wholemeal bread, from iodised bakers' salt (max 65 mg
  iodine per kg salt).
- **NEVO knows brands:** "Halvarine Jumbo", "Becel pro-activ", "Blue Band Goede Start", "Kaas Heks'n-". That's
  how the word "Jumbo" briefly counted as a food word in the matcher.
- **Dutch food words learned from the matcher:** *boerenkaas* is raw-milk cheese (NEVO "Kaas rauwmelkse");
  *veldertjes* are young marrowfat peas ("Kapucijners jonge"); *hoofdkaas* is *zure zult*.
- **RIVM's terms:** use only unchanged, cite the exact reference line, don't charge for it. So the NEVO
  files stay unchanged (the two the code reads are in this private repo), and suspicious values are overridden by *model rules* in code, never by editing data.

## The price data (Checkjebon, 2026-10-30)

- **107,271 products at 10 chains.** ALDI and Ekoplaza have no data; Poiesz (1,697 products) and Vomar (887)
  are tiny online.
- **30,108 products (28%) have no usable weight or volume** ("per stuk", "per tros", or nothing). Most fruit
  is sold per piece, which is why oranges, kiwis and many apples simply don't exist for the model.
- **Lidl's €0.01 "products"** are bookkeeping lines: "(X) Heffing SUP" (the single-use plastic levy),
  "[X] Emballage" (deposit), "+ refill verpakking". There's even a product called "23.08.2026".
- **What "price per kg" contains in this model:**
  - **peel and core removed:** bananas lose 36%, oranges 27%, apples 10%, onions 10%; eggs lose 12% shell;
  - **canned:** priced on the 60% that's drained food;
  - **oil:** priced per kg, not litre (1 L ≈ 0.92 kg).
  - So bananas at €1.93/kg on the shelf are €3.02/kg of banana you actually eat.
- **Bigger pack, *higher* price per kg** happens a lot. Some of it is real (Jumbo apple sauce: 710 g jar
  €0.69/kg vs 12 × 100 g pouches €1.91/kg). Some is a size label describing one unit of a multipack, or a
  promo price on the small pack (Lidl chicken breast 400 g €4.98/kg vs 800 g €12.06/kg; Dirk Coca-Cola 1 L
  €1.19 vs "1,8 liter" €7.49).
- **Organic costs up to 7×:** red cabbage €1.31/kg (PLUS) vs €9.54/kg (AH Biologisch).
- **Jumbo's full-fat chocolate milk is €0.75/L**: cheaper than plain milk at most chains (AH semi-skimmed
  €1.29/L, Dirk €0.89/L).

## Matcher war stories (stage 1)

Automatically matching 77k product names to NEVO foods went from **~65% to ~90% precision** over a dozen
rounds. Errors that had to be fixed:

| product | matched as | why |
|---|---|---|
| Bonne Maman Viervruchten confiture | dried beans | bonne → bon → bonen (stemming) |
| Chimay Pères Trappistes (beer) | dried pears | pères → peren |
| Slush Puppie Bon Bons | dried beans | same |
| Dove Advanced Care dragon fruit spray | muesli | "fruit" |
| Good Boy appel & cranberry (dog treat) | apple sauce | pet food |
| Pets Unlimited tonijn & garnaal | tuna | pet food |
| Spa Touch watermelon-kiwi | kiwi | flavoured water |
| Rio Mare tonijn in water | water | the medium, not the food |
| John West tonijnstukken in zonnebloemolie | sunflower oil | same |
| Brouwerij 't IJ Vrijwit (beer) | ice cream | "IJ" + s = "IJs" |
| Hollandse Winterpeen (carrots) | salted herring | NEVO's herring synonym is "Hollandse nieuwe" |
| Seepje afwasmiddel sinaasappel | orange | washing-up liquid |
| L'OR / Illy bonen (coffee) | beans | coffee beans |
| Maza Hoemoes zongedroogde tomaat | sun-dried tomato | hummus |
| Lidl Halfvolle choco melk | plain milk | "choco" unknown |
| Jumbo Kipfilet | *(no match)* | "Jumbo" is a food word (NEVO "Halvarine Jumbo") |

What fixed it:
- a real Dutch plural/diminutive matcher instead of crude stemming;
- composites and flavours caught inside compound words (*kidneybonen**soep***, *maaltijd**salade***);
- the rule that in "X in Y" or "X van Y" the food is X;
- volume-sold products (ml/l) may only match liquids;
- cheese fat classes (30+ ≠ 48+) must agree;
- brand words filtered out of the food vocabulary automatically.

**Result:** 7,848 product matches → 597 NEVO foods, 415 sold at 3 or more chains. Combined with the 50
hand-mapped staples, the catalog has **610 foods**. Hand decisions live in `data/review.tsv`.

## What the optimiser does

- **The cheapest diet uses exactly as many foods as there are binding constraints** (17 = 13 nutrients + 4
  caps on the first run). The vertex lemma from the original chat holds on real data.
- **Food caps barely matter for cost:** removing them all kept the optimum at €1.55/day, just with sillier
  amounts (246 g of raw flour).
- **The Dutch norms moved while the model was being built (2026-11-02):** Gezondheidsraad 2026/14 doubled linoleic acid to
  4 en%, halved ALA to 0.5 en% and dropped the carbohydrate number. The cheapest diet barely notices: linoleic acid was already
  well above even the new norm, and the whole package saves €0.02/day. The expensive change is women's iron: EFSA's 18%
  absorption instead of 16% costs €0.10/day. See `SOURCES.md`.
- **Removing the caps for good (2026-11-02, high-protein profile, AH):** pure LP €1.71 → €1.66/day, realistic week €2.65 →
  €2.53/day. The price is realism: 243 g of raw wholemeal flour and 125 g of peanuts in the LP, 31 g of garlic and
  141 g of peanuts a day in the realistic week.
- **Cheapest protein per euro is white pasta** (176 g/€ at €0.70/kg), ahead of peanuts (111), split peas
  (111) and lentils (88). Legumes are protein-dense but cost 3× more per kg.
- **Cheapest calories:** sunflower oil (6,453 kcal/€), white rice (5,587), self-raising flour (5,387).
- **Cheapest vitamin C** is Brussels sprouts (758 mg/€), then kale and red cabbage. Citrus barely shows up
  (sold per piece).
- **Cheapest calcium** is low-fat yoghurt (2,027 mg/€).
- **The LoSalt hack:** a low-sodium salt substitute is ~2/3 potassium chloride. At 38,000 mg potassium per
  euro it's 8× better than anything else, so the model uses 5 g a day to meet the 3,500 mg potassium norm.
  Legitimate, a bit cheeky, and sold at only one chain.
- **Every upper limit you forget gets exploited.** With 50 hand-picked foods sugar didn't matter. With 610,
  the model drank 719 g of chocolate milk a day until the WHO free-sugar limit went in.
- **Vegetarian:** with the 50 staples, infeasible (EPA+DHA 70% short). With 610 foods, feasible at
  **€4.43/day** (+€3.20): roughly four eggs a day plus 250 g of coffee creamer to scrape together 200 mg of
  EPA+DHA. An algae-oil capsule would be far cheaper.
- **Frikandelbroodje:** one a day adds €0.85/day and makes salt binding. The most that still fits every norm
  is 1.77 a day. NEVO's version: 474 kcal, 15.5 g saturated fat (29% of its energy), 1.9 g salt.
- **Cooking and absorption corrections change little** (€1.47 → €1.55 → €1.92 with every pessimistic
  assumption at once). The only expensive one is low non-haem iron absorption (5%), because 98% of the
  cheap basket's iron is plant iron.

## Stage 1 result: the expanded catalog

Cheapest adequate day (cooked, all norms incl. free sugars):

| setup | foods | €/day |
|---|---:|---:|
| 50 hand-mapped staples, cheapest chain | 50 | 1.55 |
| catalog, cheapest chain per food | 610 | **1.23** |
| catalog, only foods sold at ≥ 3 chains | 429 | 1.32 |
| only DekaMarkt | 369 | 1.42 |
| only AH | 368 | 1.54 |
| only Dirk / only Jumbo | 346 / 406 | 1.59 |
| only PLUS | 419 | 1.70 |
| only Hoogvliet | 321 | 1.76 |
| only Lidl | 286 | 1.79 |
| only Spar | 318 | 2.00 |

- **AH is not the expensive option for this kind of basket.** The cheapest optimal basket mostly uses house
  brands, and AH's are competitive.
- **Lidl looks expensive mainly because its online data often has no pack size**, so fewer of its products
  qualify. That's a data effect, not necessarily a shelf price effect.
- **New foods the catalog brought in:** Brussels sprouts, Blue Band halvarine (fortified with vitamins A and
  D), leverworst (liver sausage, cheap vitamin A and B12), self-raising flour, LoSalt.

## Cooking and absorption on the 610-food catalog

- **Cooked is now €0.01 *cheaper* than raw** (€1.23 vs €1.25). With 610 foods, the sample noise between
  NEVO's raw and cooked entries (see broccoli potassium) outweighs the real cooking losses. Cooking still
  matters per food (vitamin C), just not for the total.
- **Iron got tighter:** the cheaper basket has less spare iron, so 10% non-haem absorption now costs
  +€0.08/day (it was free with 50 foods), and 5% costs +€0.36.
- **At 5% absorption the model reaches for appelstroop** (Dutch apple syrup), which is famously iron-rich, and
  for 150 g of lentils a day.
- **Zinc at EFSA's highest phytate level (16.3 mg) costs only €0.04/day.**

## Known gaps

- **About 10% of automatic matches are wrong.** Mostly harmless, because the model uses the *cheapest* match
  per chain, but they inflate availability ("Lidl sells banana" because of a banana cake).
- **26 raw meats, fish and legumes have no cooked NEVO entry** (e.g. "Kalkoenfilet rauw"), so for those
  cooking losses are ignored.
- **Soy drinks are usually fortified, but labels rarely say so.** The matcher maps them to unfortified NEVO
  soy drink, which is conservative.
- **Plain "Bruine bonen" in a jar is dropped** as ambiguous (canned vs dried can't be told from the name).

## Stage 2: amino acids, five profiles, absorption

**Profiles, cheapest adequate day** (all chains; `compare.py` makes the per-chain table):

| profile | weight | kcal | protein | €/day |
|---|---:|---:|---:|---:|
| high-protein | - | 2,950 | 128 g | **1.47** |
| average man (35) | 73.4 kg | 2,743 | 61 g | 1.33 |
| average woman (35) | 62.5 kg | 2,165 | 52 g | 1.40 |
| active man | 73.4 kg | 3,258 | 88 g | 1.40 |
| active woman | 62.5 kg | 2,571 | 75 g | 1.43 |

- **Calories are almost free; protein and iron are what cost money.** The active man eats 300 kcal more than the high-protein profile
  and is €0.07/day cheaper. The extra cost there is protein: at 1.2 g/kg that diet would cost €1.36, the same as at
  0.83 g/kg, so everything above ~1.2 g/kg is a pure protein bill (€0.11/day for the last 0.4 g/kg).
- **The average woman eats 580 kcal less than the average man and still pays more.** All of it is iron:
  16 mg × 16% = 2.56 mg absorbed vs 1.76 for men. With the men's iron target her day costs €1.28 instead of
  €1.40. Women's iron is the single most expensive sex difference in the Dutch norms.
- **Rinse appelstroop enters both women's baskets** (60 g/day): NEVO gives it 13.8 mg iron per 100 g, more than
  liver sausage. Checked and kept (`data/review.tsv`). 60 g is about three tablespoons on bread, and it fits
  the free-sugar limit.
- **Absorption corrections:** absorbed iron (non-haem 10%) costs the average man €0.06/day; zinc at EFSA's
  high-phytate level (14 mg instead of 9) costs nothing for any profile, the cheap basket is full of zinc
  (wholemeal flour, peanuts, lentils). At 2,950 kcal neither costs anything.

**Amino acids** (USDA SR Legacy profiles × NEVO protein × digestibility, WHO 2007 per-kg needs):
- **None bind, as expected.** The tightest is always **lysine**: 1.47× the requirement for the average man,
  1.94× for the high-protein profile. Everything else is at 2× or more. Cereals are famously lysine-poor (wheat 23 mg per g of
  protein vs 84 for dairy, 86 for meat) and these baskets are mostly wheat, but the yoghurt, lentils and
  peanuts fill the gap.
- **Per gram of protein, amino acids really are stable within a kind of food:** coefficients of variation
  around 3–8% for rice, legumes, peanuts, fish and eggs. Vegetables (≈30%) and fruit (35–75%) vary a lot,
  but they barely contribute protein.
- **NEVO and USDA agree on tryptophan:** over 293 foods, NEVO's tryptophan per g protein is a median **0.96×**
  the USDA family value (10th–90th percentile 0.67–1.21). Oats, peanuts, soy, rye and legumes match within
  a few percent.
- **Where they disagree, NEVO looks odd:** gluten-free light bread has 0.02× the expected tryptophan,
  chocolate croissant 0.12×, light dairy spread 0.12×. These look like recipe-calculated NEVO entries with a
  missing tryptophan value for one ingredient. The model uses NEVO's tryptophan where present, so these few
  foods are undercounted (conservative).
- **USDA gaps:** "Vital wheat gluten" has no amino acid data (seitan gets the wheat profile); rye grain has no
  cystine (imputed from methionine with the cereal-group Cys/Met ratio). USDA's rye profile is low across
  the board, a hint that its protein value uses a different nitrogen factor.

**Healthy weight vs reality:** CBS (2025, self-reported) has men aged 30–40 at 182.6 cm and 85.7 kg (BMI 25.7),
women at 168.5 cm and 71.9 kg (BMI 25.3). At BMI 22 the reference man is 12 kg lighter and the woman 9 kg.

## Stage 3: availability, alternatives, price split

**The price split** (LP duality: at the optimum a basket food's price equals Σ_j y_j·a_ji over the binding
requirements; `reports/<profile>.md` §10). What each food is *really* bought for:
- **For the average woman, pasta is an iron supplement:** 53% of white pasta's price pays for absorbed iron,
  61% of wholemeal pasta's. Apple syrup is 88% iron. Her whole basket bends around iron: dropping the iron rule
  would save **€0.26/day**, 18% of her diet.
- **For the average man, yoghurt is bought for calcium (43%) and riboflavin (39%);** for the high-protein profile it's riboflavin
  (41%) and protein (35%). Same food, same price, different reasons, because the shadow prices differ.
- **Brown rice for the average man is 39% energy, 31% selenium.** Blue Band halvarine is a vitamin pill:
  riboflavin and B6 (it's fortified), not fat.
- **Energy can be a penalty, not a need.** At 1.6 g/kg, 128 g protein drags calories against the energy maximum,
  so every calorie-dense protein food has a negative "energy" share: 25% of pasta's price, 14% of peanuts'.
  For the reference profiles energy is a *positive* share instead: they're bought partly for calories.
- **Cap rent:** apple syrup at the women's cap (the model's daily maximum) is worth €0.14/100 g more than it
  costs; she'd eat more if allowed.
- **The identity holds to machine precision** on every basket food (`explain.price_split` asserts it).

**What replaces what** (§11, three levels of "remove the biggest food"):
- **The optimum is very flat.** Removing the three biggest foods one after another costs at most €0.14–0.17/day
  depending on the profile; no single removal costs more than €0.08. Yoghurt is replaced by skimmed milk, milk by chocolate milk, pasta
  by self-raising flour and bread, flour by rice. Cheap Dutch staples are close substitutes in nutrient space.
- **Different removal orders often reach the same diet** (the report says so instead of repeating it): the LP
  vertex depends on the *set* of foods left, not on the order you took them away.

**What each rule costs** (§12, drop one requirement):
- **High-protein profile:** protein is the most expensive rule (€0.12/day), then vitamin C (€0.05), selenium (€0.04).
- **Average man:** calcium (€0.09), absorbed iron (€0.07), vitamin C (€0.05).
- **Average woman:** absorbed iron (€0.26), calcium (€0.14), vitamin C (€0.05).
- **Potassium is cheap only because of LoSalt** (the KCl salt substitute, sold at one chain). Restricting to
  foods sold at ≥ 3 chains costs the average man €0.07/day, almost all of it LoSalt leaving; for the high-protein profile nothing.

**Data errors the hand-check found** (every product of every food in any alternative, 39 foods):
- **Lentils without "dried" on the label were priced as dried.** "AH Terra Linzen 400 g", Lidl "Linzen 400 g",
  "Mediza Linzen", "PLUS Linzen"…: 360–400 g are can and jar sizes, and cooked lentils weigh ~2.4× dried, so
  they looked 2.5× too cheap per cooked portion. Lidl's was the cheapest "dried lentil" in the country. Now
  treated as canned. This alone raised the women's diets by €0.04/day.
- **A bug since stage 1:** when an automatic match beat a hand-mapped *canned* food's own price, the 60%
  drained-weight factor was dropped (`catalog.py`), so canned legumes at those chains came out 40% too cheap.
- **Mussels were priced with their shells:** NEVO's raw mussels are per 100 g of meat, a 2 kg bag holds about
  400 g. Now 20% edible (rule of thumb: ~200 g meat per kg). Fresh oysters in the shell: excluded.
- **Also caught:** a seed cracker and a seed bar sold as sunflower seeds, baby food (Olvarit beet mash with
  chickpeas) as canned chickpeas, dried kidney beans as canned ones, frozen kale cubes as raw kale, and Rio
  Mare "Insalatissime" (ready-made tuna salads) as lentils, couscous and sweetcorn.

## Stage 4: whole packs at one chain

`plans.md` (`plan.py`): the cheapest basket bought as real packs at one chain, as a repeating weekly list and as a
4-week rotation. Fresh food in whole packs within its shelf life (waste is paid for), pantry food per gram,
stored nutrients on the 4-week average, at most 10 kg in the freezer.

- **Whole packs cost almost nothing:** +€0.01 to +€0.03/day over the pure LP at the same chain for four of the
  five profiles. The cheap basket is mostly pantry food (flour, pasta, peanuts, lentils, oil) whose packs
  simply carry over; only bread, yoghurt, sprouts and liver are fresh.
- **Except when a chain only sells a big bag.** DekaMarkt and Dirk sell Brussels sprouts only in 1 kg bags, so
  a person alone either wastes most of it or eats 143 g a day. That costs DekaMarkt €0.12/day and **flips the
  chain ranking**: per gram DekaMarkt is the cheapest chain for the high-protein profile (€1.64/day), in whole packs AH wins (€1.73
  vs €1.76). AH's sprouts come in 450 g.
- **The 4-week rotation saves at most €0.01/day.** Stored nutrients could in principle be bought once a month
  (one tin of herring, one pack of liver), but the pantry already provides them cheaply every week. Its real
  use will be variety in stage 5.
- **The freezer makes bread a monthly buy:** the weekly plan buys 10 loaves every 4 weeks (6 kg frozen), the
  rotation buys 6 + 2 + 2 in weeks 1, 2 and 4. Uneven weekly spending is the price: €6.75, €9.04, €1.05, €7.20
  on fresh food in the four rotation weeks.
- **The 30%-of-energy rule never binds** in the cheapest plans and dropping the "≥ 3 chains" rule saves nothing
  at one chain: the "crazy" list's only real saving is shopping at every chain at once (€0.26/day for the high-protein profile).
- **Pet food kept sneaking in:** "Perfect Fit Droogvoer … zalm" and "Jumbo Biologische Kattenpaté Zalm" were
  accepted as tinned salmon, Iams and Gourmet cat food as tinned tuna, Frolic dog food as raw beef. The pet
  filter knew Whiskas and Felix but not these brands; it now catches *katten*, *honden*, *droogvoer* and
  *natvoer* anywhere in a name. A remap of salmon fillets to raw salmon was tried and reverted: remaps skip the
  filters, and it immediately pulled in "Pets Unlimited Zalmfilet strips".
- **A pack's weight isn't what you eat:** pack prices must be divided over the *edible* grams (peel, bones, can
  liquid). The first version of the plan priced packs on the label weight and came out cheaper than the LP.

## Stage 5: meals and dishes

**NEVO's dishes, priced from their ingredients** (`dishes.py` → `dishes.md`):
- **At first only 4 of the 99 dishes could be priced at AH.** NEVO's recipes use prepared ingredients ("onion
  boiled", "potatoes boiled") and specific products ("salt *without* iodine", "Parmesan", "beef poulet"). With
  cooked → raw by name (buy raw, same cooking yields as the catalog), a close substitute in the same food group
  with the same head noun, and the median vegetable price for vegetables sold only per piece (celery, cucumber,
  courgette), **53 dishes at AH** (45–55 at the big chains).
- **Sugar, wheat flour and tomato paste weren't in the catalog at all:** they're basic foods with a weight, but
  the matcher never accepted them. Sugar alone blocked 14 dishes. Added by hand.
- **Substitution by "any shared word" is a trap:** red pepper became red *onion* ("rode"), pork mince became pork
  *liver* ("varkens"), green pepper became green *asparagus*. Dutch NEVO names start with the head noun, so the
  first word now has to match.
- **The cheapest dinners per 500 kcal are Surinamese and Dutch:** roti (€0.32), dahl (€0.44), risotto (€0.58),
  then the stamppotten. Pizza from scratch costs ~€1.45 per 500 kcal, an omelette €1.64.
- **More baby food:** "Olvarit Groente ringen 12m+" was the "Vegetables av raw" at AH, at €72/kg, and Olvarit or
  Ella's Kitchen jars were matched as plain apples, bananas, peas, cauliflower and rice flour. Also "Flower Farm
  Bakken zonder palmolie" (frying fat *without* palm oil) as palm oil and a vegan tuna as vegetable oil.

**A week of meals** (`meals.py` → `meals.md`): brunch + warm dinner + snacks, dinners are NEVO
dishes, six soft rules, medium strictness (a rule bends only if that saves ≥ €0.25/day).
- **High-protein profile: €2.65/day** at AH: hutspot ×2, stamppot zuurkool ×2, risotto ×2, an omelette with pasta; porridge, 8
  slices of wholemeal bread, peanuts. **Real meals cost €0.91/day more than the bare basket** (€1.73), mostly
  because raw flour can no longer be "eaten", sides need a dinner that takes them, and pasta, garlic and bread
  have normal-size caps.
- **The one rule that bends is fruit:** 200 g a day would cost €0.33/day. Fruit is expensive here mostly because
  it's sold per piece, so the data has hardly any priced fruit.
- **Every other rule is free:** 4 different dinners, none more than twice, 2 toppings, 250 g vegetables, no food
  above 30% of energy. Loose strictness (bend for ≥ €0.10) saves €0.22/day by repeating dinners.
- **Dinners stay at the minimum portion (300 g)** and leftovers are never used: per nutrient, NEVO's dishes are
  dearer than bread, oats and peanuts, so the optimiser eats just enough dinner. **Batch cooking isn't used
  either:** the cheapest dinners are quick ones.
- **The reference profiles land at €2.44–2.65/day** with the same dinners. The cheap Dutch week is stamppot.
- **First version ate 31 g of raw garlic a day** (about ten cloves) as a "vegetable" and 250 g of dry pasta next
  to stamppot. Foods eaten as such now have normal caps, and pasta, rice or potatoes as a side need a dinner that
  takes a starch side.

## Stage 6: the app

- **The removal tree is shallow near the top.** Take the fortified soy drink out of the AH basket and the cost
  rises by just **€0.007/day**: 220 g extra low-fat yoghurt does the same job. Removing the bread (+€0.04) or the
  yoghurt (+€0.04) is cheap too; you have to remove two staples before it hurts (bread *and* yoghurt: +€0.12).
- **The wiggle room is huge for foods that aren't in the optimum at all.** Within 5% of the cheapest cost you can
  eat up to **470 g frozen peas and carrots** or **460 g milk** a day, both at 0 g in the optimum. The
  near-optimal polytope is wide and flat: many very different diets cost almost the same, which is why tiny
  price changes can swap foods in and out of the basket.
- **Protein is the expensive requirement to push.** At AH: 1.25× protein costs €2.23/day, 2× (256 g) €5.52/day,
  and at **2.5× (320 g) there is no diet at all**: with energy capped at 104% of 2,950 kcal and carbs ≥ 40% and fat
  ≥ 20% of energy, there's no room left for that much protein. Drop either energy-share rule and it's feasible
  again (€8.48). Calcium doubles for +€0.38, vitamin C quadruples for +€0.24.
- **Fibre is free up to 1.5×** (the basket already has 153% thanks to wholemeal bread and flour), then climbs
  steeply: 4× costs €3.64/day.
- **Shadow prices at AH:** the dearest requirements per unit are riboflavin (€0.18 per mg) and EPA/DHA (€0.15 per
  g). Protein's shadow price is €0.006 per g, so the 128 g floor itself "costs" about €0.73 of the €1.71.
- **Poiesz and Vomar look absurdly expensive** (€6.76 and €9.09/day for the high-protein profile) only because their online ranges in
  Checkjebon are tiny: the LP has to build a diet from a handful of foods. The chain chart leaves them out; the
  table under it keeps them.
- **Streamlit quirk worth knowing:** its chart theme quietly overrides Altair's font sizes and squeezes row
  heights when a chart stretches to the page width, so labels skip and stacked bars overlap. The app renders
  charts with `theme=None` and an explicit pixel height.

## My foods and category ticks (2026-11-02)

Prices in this section are for the high-protein profile at AH.

- **What 500 g of milk a day does (pure):** €1.64 → €1.72. It costs €0.47 itself, but €0.39 comes back: soy drink
  drops from 283 to 59 g, yoghurt (186 g) and white pasta (167 g) leave, and peanuts double to 211 g, presumably to replace the
  energy of the pasta.
- **Milk is nearly free until it suddenly isn't:** 250 g +€0.04, 1 kg +€0.32, 1.5 kg +€0.66, then 2 kg +€10.70, and 2.5 kg is
  impossible. Calcium is the wall: 1 kg of milk has 1,230 mg and the maximum is 2,500 mg, so at 2 kg the rest of the diet has
  to be almost calcium-free. Just below a limit the shadow price explodes, a nice picture of the polytope closing.
- **Which food groups the cheapest diet actually needs (+€/day to remove):** vegetables 0.73, grain products 0.59, supplements
  0.22, nuts 0.17, seeds 0.06, meat 0.05, dairy 0.01. Eggs, fruit, potatoes, legumes and soy cost under a cent: the cheapest
  basket hardly uses them, or swaps them for something almost as cheap.
- **Fish is the expensive one:** +€2.06, and vegetarian (no meat, no fish) is €4.22/day. The EPA+DHA minimum does all of it:
  without that one limit, no fish costs €1.61 and vegetarian €1.74.
  Vegan is impossible under the model's rule that plants have 0 EPA+DHA; it's the only limit in the way.
- **Without the vitamin D tablet:** +€0.22/day, about 13 times the tablet's €0.017. It's the best deal in the basket.
- **Soy drink is "dairy" in the catalog's groups,** so a first "no dairy" test also removed soy drink and cost +€0.65. With soy
  drink kept, no dairy costs +€0.01, and no soy with dairy kept costs under a cent. Either one is nearly free to lose; losing
  both isn't.
- **Category war stories:** "self-raising" flour came out as fruit, because it contains "raisin", and "Salad cream" as dairy. The
  name rules need guards from the start: "Egg whole chicken" and "Lettuce lambs" aren't meat, and NEVO's "wo" (without) has to
  cancel the next word, or "Puff pastry wo butter" is dairy.
- **"Beef av raw" had egg and bread crumbs in it:** one kind in the average (11%) is a meatball. Averages now only take on what
  at least half of the mix has.
- **NEVO's typical recipes hold surprises:** hummus has 17% peanut oil, and so does cucumber salad (17.5%). The coconut ice cream
  alternative has 1% pecans. With "no nuts" they all go.
- **A spoon of oil is in almost everything:** only 3 of the 34 dinners have no fat or oil anywhere in their recipe, 19 have no
  added salt, and 5 have no vegetables.
- **Duality with a floor under a food:** a food you force in sits on its lower bound, so its reduced cost can be positive while
  it's in the basket. c = Σ y·a no longer holds for it, and `price_split` now carries that term.
- **Streamlit quirk, a real bug for a while:** a selectbox whose list of options changes falls back to its first option, unless
  you set its value yourself first. Going from realistic back to pure quietly moved the chain from AH to "all chains", so the
  price dropped from €1.64 to €1.41 with nothing on screen saying why. Only a run in a real browser showed it.
- **Which chain is cheapest depends on what you ask (average man, cooked, 2026-10-30 prices):** Dekamarkt wins both the pure LP (€1.41) and the real week (€2.24), but the rest reshuffles. Dirk is second in the pure LP (€1.49) and fifth for a real week (€2.52); Lidl goes from seventh (€1.82) to second (€2.35). Whole packs and dinners decide that, not the bare food prices.
- **Vomar's real week is cheaper than its pure LP:** €5.38 against €6.34 for the average man, with 3 meal rules bent. The LP should be a lower bound on the same foods, so the dishes are probably adding something the LP can't buy there. Not looked into yet; Vomar is nowhere near winning.
