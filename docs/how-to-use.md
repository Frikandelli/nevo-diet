# How to use nevo-diet

## The screen

- **The sidebar on the left** is what to solve. Work down it from 1 to 6; the most important settings are at the top,
  the optional ones folded away at the bottom. Hover over the small (?) next to a setting for what it does.
- **The pages along the top** show the result. Start on **Plan**.
- **Pure** plans update as soon as you change something. **Realistic** plans wait for the **Solve** button in the
  sidebar (10-20 seconds; anything you solved before shows at once).
- Tick boxes in tables (✗, ✗ kind, cook, the category ticks) wait for **Apply**, so you can tick several in a row.

## In six steps

1. **Who eats.** Pick a profile: average or active, man or woman. It sets every nutrient limit and the estimates
   of calories and protein. Make your own on **Profile & limits**.
2. **Calories and protein.** The two numbers that shape the diet most. Leave them blank to use the estimate (in grey),
   or type your own. *Your body* underneath (weight and height) only feeds those estimates.
3. **Where you shop.** Pick a chain, or *cheapest chain* to let the app find it.
4. **Kind of plan.** *Pure* is the mathematical minimum; *realistic* is a week of meals with a shopping list (press
   **Solve**).
5. **Fewer foods.** Keep the *cost per food* at €0.05: it stops the plan from using a gram of this and a gram of that.
6. **Supplements.** Only the vitamin D tablet unless you change it on the **Supplements** page.

Then read the **Plan** page: the price, the foods, and whether every nutrient limit is met.

## What every setting does

| Setting | What it does | Default | Change it when |
|---|---|---|---|
| **Profile** | Sex, age, body and activity of the person eating. Sets every nutrient limit (women need more iron, men more zinc ...) and the calorie and protein estimates. | Average man | Always: pick the one closest to you, or make your own on Profile & limits. |
| **Calories** (kcal/day) | The energy target. The diet lands between this number and 4% above it. Blank: estimated as resting energy (from weight, height, sex and age) × activity level. | the estimate | You know what you need, or want to eat less (lose weight) or more. |
| **Protein** (g/day) | The least protein a day; the diet may have more. Blank: the profile's grams per kg × weight (0.83 g/kg, the Dutch norm; 1.2 for the active profiles). | the estimate | You train (1.4-2.0 g/kg is common), or follow a diet that says otherwise. More protein is the most expensive change you can make. |
| **Weight** (kg) | Only for estimates: calories and protein when those are blank, and the amino acid needs (in mg per kg). | the profile's | Your weight differs from the profile's. |
| **Height** (cm) | Only for the calorie estimate (the Henry equation behind the Dutch norms). | the profile's | Your height differs from the profile's. |
| **Chain** | Whose prices are used: the cheapest product of each food at that chain. *Cheapest chain* tries them all and picks the one where your plan costs least. *Every chain* (pure only) takes each food from wherever it's cheapest, which no single shop can match. | Albert Heijn | You shop elsewhere, or want to know where it's cheapest. |
| **Kind of plan** | *Pure*: the bare linear program, grams per day of any food. *Realistic*: a week of real dinners (NEVO dishes), bread toppings and snacks, bought in whole packs at one chain, with a shopping list. | pure | You want something to cook and shop from: realistic. |
| **Strictness** (realistic) | How firmly the meal rules hold: at least 4 different dinners a week and none more than twice, 2 bread toppings, 250 g vegetables and 200 g fruit a day. Strict: never bent. Medium: bent if that saves €0.25/day. Loose: if it saves €0.10/day. None of these rules limits how much of a food you eat: that is up to your own limits (below). | medium | You want more variety (strict) or a cheaper week (loose). |
| **Meals** (realistic) | Brunch + warm dinner (cooked with leftovers for the next brunch) + snacks, or breakfast, lunch and dinner. | brunch | You eat three meals a day. |
| **Batch cooking** (realistic) | One weekend session for dried pulses and soup, frozen in portions. | on | You don't want to cook ahead. |
| **Cost per food** (€/day) | A small charge for every food in the plan, so a food only comes in if it saves at least that much. It isn't in the price shown. | €0.05 | 0 for the textbook answer; 0.10 or more for a shorter shopping list. |
| **Whole fruit** (optional) | A minimum of whole fruit in grams a day (not juice, jam or dried fruit). The cheapest diet has none: other foods give the same vitamins for less. | 0 | You want fruit in the plan (the Dutch guideline is 200 g). |
| **Budget** (optional) | Only a check: the Plan page says whether the plan fits, the cost curves draw it as a line. It never changes the plan. | €3.00 | You want to see how far below your budget the plan is. |
| **Only foods sold at ≥ 3 chains** (optional, pure) | Leaves out foods that few chains sell: often matching errors, or hard to find. | off | A plan uses something odd or rare. |

### Why the cost per food saves money

The pure plan pays per gram, so 1 g of kale a day costs a fraction of a cent on paper. In the shop it is a whole bag,
most of which you throw away. The cost per food makes every extra food "cost" €0.05 a day, so the plan only keeps foods
that are worth it. The food itself gets a few cents dearer on paper (the Plan page says how much), but the shopping list
gets shorter and real shopping cheaper.

## Leaving foods out, and putting them back

| You want to leave out | Where |
|---|---|
| **One food** | Tick **✗** in the plan table (Plan page) or the foods table (Foods page), then **Apply**. |
| **A whole kind**: all pasta, all rice, all wheat flour, oily fish, cabbages ... | Tick **✗ kind** in the plan table, or pick it under *Leave out or put back foods and kinds* (Plan page) or *Leave out whole kinds* (Foods page), then **Apply**. |
| **A whole category**: no meat, no fish, no dairy, no grain products ... | The category ticks on the Foods page. |
| **An allergy or intolerance**: gluten, lactose, milk, egg, nuts, soy ... | The allergy ticks on the Foods page. Worked out from names and typical recipes: still read every label. |

**To put something back:** remove it from the lists in *Leave out or put back* (Plan page), untick it on the Foods
page, or use **Put back all foods** there. The sidebar says how many foods are left out.

A kind is finer than a category: *no grain products* removes flour, pasta, rice, oats and bread together; the kind
*pasta and noodles* only the pasta. In the realistic week, leaving a food or kind out also removes the dinners made
with it. Foods you put in **My foods** always stay in.

## Limits: at most so much of a food or a kind

There are **no limits on foods by default**: the plan may use any food in any amount, so a cheap one can end up at
400 g a day (wholemeal flour, often). To cap it, go to the Plan page → **Limits** → type a food or a kind (*pasta and
noodles*, *bread*, *cheese* ...) → set *at most* so many grams, per day or per week.

- **A kind's limit is for all its foods together:** *bread at most 150 g a day* is 150 g of all breads, not 150 g each.
- **It counts everything you eat of it,** in grams as bought (dry pasta, raw meat): on its own and, in the realistic
  week, as an ingredient of the dinners. A potato limit also limits hutspot.
- **0 g means none at all,** in dinners too: the same as ✗ kind. Above 0, dinners with a little of it can stay, as
  long as the total fits under the limit.
- **In the plan:** a food at its limit says *at your limit*; the nutrient check lists your limits under *your limits on
  foods*, and says when one sets the price. *Why this diet* → *What each limit costs* shows what a limit costs you.
- **Too tight?** If no diet fits, the Plan page names the limit in the way. A limit below what you ask for in **My
  foods** can't be met either; the message says so.

Minimums are **My foods** (*at least* or *exactly*); maximums are **Limits**. Both are saved on your computer and stay
when you switch profile. *Reset everything* (Settings) removes them.

## Supplements: pills next to food

The **Supplements** page lists 28 vitamin and mineral pills, multivitamins, fish and algae oil and psyllium, each with
its cheapest price and what it would save. **By default the plan only uses the vitamin D tablet**; the sidebar's step 6
says what it may use now.

- **Which ones the plan may use:** *only the ticked ones* (tick **use**), *every supplement with a price*, or *every
  supplement*, where one without a price counts as free. Press **Apply** after changing anything.
- **Prices:** each supplement's cheapest product. *Buy supplements at any shop* (on by default) includes drugstores and
  every chain, because pills keep for a year; off, only your chain counts. A supplement without a price shows **€0 ⚠**.
  Type a price in *€ per unit* (pack price ÷ tablets) to use your own; *Forget my prices* undoes that.
- **Exactly:** give a supplement an exact amount, per day or per week (*1 per week* of B12 1000 µg), and the plan
  takes exactly that whatever it costs, as with *exactly* in My foods.
- **saves €/day:** what a supplement is worth to the plan: for one it may not use yet, what ticking it alone would
  save; for one it may use, what it saves now.
- **Counted as the norms count it,** not as the label says: folic acid ×1.7, synthetic vitamin E ×0.67, and a big B12
  tablet only for what the gut takes up (1000 µg counts as 22 µg). *How a label is counted* on that page has every rule.
- **On the Plan page** a supplement is a row like a food, in tablets a day (pure) or whole tablets a week (realistic),
  with its shop. If the price includes a free one, the Plan page warns.

## Common tasks

- **"I eat 500 g of yoghurt a day anyway."** Plan page → *My foods* → add yoghurt, 500 g per day, *exactly* (or *at
  least*, if more is fine). The plan fills in the rest and shows what your yoghurt changed.
- **"No pasta for me."** Tick **✗ kind** on the pasta row, then **Apply**. The price tile shows what it costs.
- **"Not 400 g of flour a day."** Plan page → *Limits* → add *wheat flour* (the kind) → at most 50 g per day.
- **"At most 3 eggs a week."** *Limits* → add the egg → at most 180 g per week (about 60 g an egg).
- **"I'm vegetarian."** Foods page → tick *No meat* and *No fish* → **Apply**. If no diet is possible, the Plan page
  names the limit in the way; you can change that limit on Profile & limits.
- **"I want a shopping list."** Sidebar → *realistic* → **Solve**. The Plan page then has the dinners, what's eaten as
  such, and the shopping list per week.
- **"Where is it cheapest?"** Sidebar → Chain → *cheapest chain*. The *Every chain compared* section on the Plan page
  has the others; *Why this diet* has them as a chart.
- **"Why is this food in my plan?"** Why this diet → *What each food pays for*: its first colour is the main reason.
- **"What if I drop the biggest food?"** Why this diet → *What replaces what*.
- **"How much would more protein cost?"** Why this diet → *Cost curves*, or type a higher protein target and watch
  the price.
- **"Save my plan."** Plan page → *The whole plan (ZIP)*: every table as a spreadsheet file, the settings, and the
  sources. Every table also has its own *Download CSV*.
- **"My own body and needs."** Type your calories and protein in the sidebar, or make a full profile on Profile &
  limits (sex, age, weight, height, activity, protein per kg, and any limit you want to change).
- **"Fresh prices."** Settings → *Fetch new prices* (about 2 minutes). Supermarket supplement prices refresh too.
- **"Would a multivitamin make it cheaper?"** Supplements page → *saves €/day* column, or *every supplement with a
  price* → **Apply**, and compare the price on the Plan page.
- **"I take B12 once a week."** Supplements page → the B12 1000 µg row → *exactly* 1 per *week* → **Apply**.

## Reading the plan

- **€ per day / week / month.** What the food costs at the chain. With your own foods or ticks, the small arrow says
  what they changed against the plan without them.
- **Amounts are as bought:** dry pasta, raw meat, peeled banana. *cook* says whether a food counts as cooked (its
  vitamins after boiling) or raw.
- **The nutrient line** says whether every limit is met and which ones *set the price*: those limits are met exactly,
  and relaxing them would make the diet cheaper. The Nutrients page has the charts.
- **Something odd in the plan?** About 10% of the automatic product matches are wrong, and the optimiser finds every
  one of them. Tick ✗ on the food; *Data & sources* says how the data was made.
- **No plan at all?** The Plan page names the limit in the way (a nutrient, or one of your limits on foods), and for
  your own foods how much would still work.
