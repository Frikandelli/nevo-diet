# About nevo-diet

**What is the cheapest way to eat everything your body needs, buying real products at a Dutch supermarket?**
nevo-diet answers that with a linear program, Stigler's diet problem from 1945, on today's data: the Dutch food
composition table (NEVO 2025), the prices of 10 supermarket chains (Checkjebon) and the Dutch nutrient norms. Then it
turns the answer into something you could live on: a week of meals, whole packs and a shopping list at one chain.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

## How it works

1. **Foods.** 107,271 supermarket products are matched by name to 608 basic NEVO foods, each with its cheapest product
   at each chain, priced per 100 g of the part you eat.
2. **Limits.** Your profile (sex, age, body, activity) sets 43 limits: energy, protein, fibre, fats, 24 vitamins
   and minerals (with upper limits where there are any), and the nine essential amino acids.
3. **The cheapest diet.** The linear program picks grams per day of each food so that every limit is met at the lowest
   price. This is the **pure** plan: the bare mathematical answer, in odd amounts.
4. **A real week.** The **realistic** plan is a mixed-integer program on top: dinners are real NEVO dishes, food is
   bought in whole packs at one chain, and meal rules keep it varied (at least 4 different dinners, 250 g of
   vegetables a day ...). A rule may be bent if keeping it costs too much, and the app says what it would cost. No rule
   caps how much of a food you eat: there are no limits on foods until you set your own (Plan page → *Limits*).
5. **Why.** The dual of the linear program prices every limit (its *shadow price*). From that the app shows why each
   food is in the diet, what each limit costs, and what would replace a food you don't want.

## Getting started

Work down the sidebar from 1 to 6 (who eats, calories and protein, where you shop, kind of plan, cost per food,
supplements) and read
the result on the Plan page. The **How to use** page (`docs/how-to-use.md`) explains every setting, how to leave out
foods and whole kinds of food and put them back, and the common tasks step by step.

## Words used in the app

- **Pure / realistic.** Pure: the linear program alone (any food, any amount, several chains if you like). Realistic:
  a week of meals with whole packs at one chain.
- **Binding, sets the price.** A limit the cheapest diet meets exactly. Relaxing it would make the diet cheaper;
  relaxing any other limit (a little) changes nothing.
- **Shadow price.** What the cheapest diet saves per unit when a binding limit is relaxed: € per mg of calcium, say.
- **Worth.** What a food's nutrients are worth to this diet: Σ shadow price × content. A food in the diet is worth exactly
  its price; every other food is worth less.
- **Reduced cost.** Price minus worth: how much cheaper a food must get before the diet would use it.
- **Price split.** A food's price divided over the limits it helps meet. Its biggest part is why it's in the diet.
- **Wiggle room.** How much a food can vary in some adequate diet that costs at most 5% more than the cheapest.
- **Limit on a food.** Your own maximum for a food or a whole kind (all bread, all pasta ...), in grams as bought a day
  or a week, dinners' ingredients included. None by default.
- **Cost per food.** A small fixed cost (default €0.05 a day) for every food in the basket, so the plan doesn't use 1 g
  of something to save a fraction of a cent. It isn't part of the price shown.
- **en%.** Percent of the day's energy (fat 9 kcal per gram, protein and carbohydrate 4).
- **Absorbed iron.** The iron the body takes up: 25% of haem iron (meat, fish) and 10% of the rest.

## What it is not

- **Not medical or dietary advice.** It's a calculation on public data. The allergy ticks are worked out from names
  and typical recipes, not from allergen data: read every label.
- **Not a menu you'd want every day.** The cheapest diet is cheap because it is monotonous: with no limits on foods it
  happily eats 400 g of flour a day. The realistic plan's rules help, and your own foods, limits and ticks help more.
- **Not complete.** About 10% of the automatic product matches are wrong, prices change every week, and taste isn't in
  the model. The Data & sources page lists every assumption.

## Credits

Food composition: NEVO, RIVM. Prices: Checkjebon, a community dataset of Dutch supermarket prices (MIT). Amino acids
and cooking losses: USDA. Norms: Voedingscentrum, Gezondheidsraad, EFSA and WHO. The data belongs to its sources (see
Data & sources). Built with Claude Code.
