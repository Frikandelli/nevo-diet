"""The "no ___" ticks: which foods and dinners fall in which category.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

A NEVO entry's categories come from three places (model rules; NEVO's values stay untouched):
  1. NEVO's own food group (cheese -> dairy, bread -> grain products);
  2. its English name, for what the group doesn't show (butter is filed under fats but is dairy, a soy drink is filed
     under dairy substitutes but is soy, "breaded" means bread crumbs). "wo" (without) and "not" cancel the next word;
  3. NEVO's recipe file, walked to the bottom: an entry made with peanut oil counts as nuts. An average ("Beef av raw", a
     mix of kinds of one food) only takes on what at least half of the mix has.

Only the categories in FOLLOWS_INGREDIENTS pass from an ingredient to what it's made with. The cooking basics (oil, salt,
sugar, yeast) don't: nearly every dinner has a spoon of oil, so "no fats and oils" would leave nothing to cook. Those ticks
stop you eating the food as such; `basics_in_dinners()` is how a dinner keeps its spoon of oil.

These are preferences, not allergy protection: NEVO's recipes are typical ones, and a real product can differ or carry
traces of anything.
"""
import csv
import re

import dishes as D

# key, label as shown after "No ...", what it covers. Every food in the catalog has at least one (test_app.py checks).
CATEGORIES = [
    ("meat", "meat", "meat, poultry, cold cuts"),
    ("fish", "fish", "fish, shellfish"),
    ("eggs", "eggs", "eggs and what's made with them"),
    ("dairy", "dairy", "milk, yoghurt, cheese, butter; not plant drinks"),
    ("legumes", "legumes and soy", "beans, lentils, chickpeas, tofu, soy drink"),
    ("plant", "plant-based alternatives", "plant drinks, tofu, tempeh, vegetarian burgers"),
    ("grain", "grain products", "pasta, rice, flour, oats, bread, crackers"),
    ("nuts", "nuts", "nuts, peanuts, peanut butter, peanut oil, chestnuts; not coconut"),
    ("seeds", "seeds", "sunflower seeds, linseed, chia, sesame; not their oils"),
    ("veg", "vegetables", "vegetables, vegetable juices"),
    ("fruit", "fruit", "fruit, fruit juices, jam"),
    ("potatoes", "potatoes", "potatoes, sweet potatoes, cassava"),
    ("fats", "fats and oils", "oils, margarine, butter"),
    ("sweets", "sweets", "sugar, syrup, chocolate spread, sprinkles, jam"),
    ("juices", "juices", "fruit and vegetable juices"),
    ("spreads", "spreads and salads", "sandwich salads, hummus, peanut butter"),
    ("snacks", "snacks", "savoury snacks"),
    ("salt", "salt", "salt"),
    ("yeast", "yeast", "yeast"),
    ("supplements", "supplements", "the vitamin D tablet"),
]
LABEL = {k: label for k, label, _ in CATEGORIES}
# A dinner or composite food with this as an ingredient counts as having it. The rest only cover the food itself.
FOLLOWS_INGREDIENTS = {"meat", "fish", "eggs", "dairy", "legumes", "grain", "nuts", "seeds", "veg", "fruit", "potatoes"}

BY_NEVO_GROUP = {
    "Vegetables": "veg", "Meat and poultry": "meat", "Cold meat cuts": "meat", "Pastry and biscuits": "grain",
    "Cereal products and types of flour": "grain", "Milk and milk products": "dairy", "Bread": "grain", "Cheese": "dairy",
    "Sugar, sweets and sweet sauces": "sweets", "Fruits": "fruit", "Fish, crustacean and shellfish": "fish",
    "Savoury snacks": "snacks", "Fats and oils": "fats", "Meat substitutes and dairy substitutes": "plant",
    "Potatoes and tubers": "potatoes", "Legumes": "legumes", "Savoury bread spreads": "spreads", "Eggs": "eggs"}

_rx = lambda s: re.compile(s)
# category -> (the name has this, unless it also has that)
BY_NAME = {
    "nuts": (_rx(r"peanut|almond|cashew|walnut|hazelnut|pistachio|pecan|macadamia|chestnut|\bnuts?\b|\bbrazil\b|satay"),
             _rx(r"water chestnut")),
    "seeds": (_rx(r"\bseeds?\b|sesame|tahin|linseed|poppy|\bchia\b|\bhemp\b"), _rx(r"^oil\b|^margarine")),
    "dairy": (_rx(r"\bmilk\b|milkchocolate|cheese|\bcream\b|yoghurt|yogurt|quark|custard|\bbutter\b|kefir|\bwhey\b|"
                  r"mascarpone|chocolate \w+ white|chocolate white"),
              _rx(r"plant-based|coconut|\bsoya?\b|almond|peanut butter|nut butter|cocoa butter|butter bean|crackers|"
                  r"creamer powder|\boat drink|drink oat|salad cream")),
    "meat": (_rx(r"chicken|\bbeef\b|\bpork\b|\bham\b|bacon|sausage|turkey|\blamb\b|\bveal\b|\bliver\b|\bmeat\b|salami|"
                 r"frikandel|gammon|brawn|\bduck\b|\brabbit\b|kromesky|kebab|gyros|shoarma|hamburger"),
             _rx(r"^egg\b|vegetarian|plant-based|meat substitute|tomato")),
    "fish": (_rx(r"\bfish\b|salmon|\btuna\b|herring|mackerel|sardine|anchov|shrimp|prawn|\bcrab\b|mussel|\bcod\b|trout|"
                 r"lobster|plaice|pollock|\beel\b|\bsquid\b"), None),
    "eggs": (_rx(r"\beggs?\b|omelette|mayonnaise"), None),
    "legumes": (_rx(r"soya|\bsoy\b|tofu|tempeh|falafel|hummus|lentil|chickpea|peas chick|\bbeans?\b|peas split"),
                _rx(r"coffee|cocoa")),
    "grain": (_rx(r"\bbread\b|breaded|crumbs|\bflour\b|\bwheat\b|\brye\b|\boats?\b|\brice\b|pasta\b|noodle|macaroni|"
                  r"spaghetti|semolina|couscous|bulgur|seitan|gnocchi|pastry|biscuit|cracker|muesli|barley|spelt|"
                  r"tortilla|pizza|dough|pancake|schnitzel vegetarian|schnitzel/burger vegetarian"),
              _rx(r"^oil\b|potato starch|flour (almond|coconut)")),
    "fruit": (_rx(r"\bfruit\b|\braisins?\b|\bjam\b|syrup apple|^juice (?!carrot|beetroot)"), None),
    "veg": (_rx(r"coleslaw|^juice (carrot|beetroot)|^tomato juice"), None),
    "potatoes": (_rx(r"potato"), None),
    "salt": (_rx(r"^salt\b"), None),
    "yeast": (_rx(r"^yeast\b"), None),
    "juices": (_rx(r"^juice\b|^tomato juice"), None),
}
# Filed under flours and cereals by NEVO, but not made of grain.
NOT_GRAIN = {"potato starch": "potatoes", "flour almond": "nuts", "flour coconut": "fruit"}
AVERAGE = re.compile(r"\bav\b")      # "Beef av raw": a mix of kinds of one food, not a list of what's in it
_CANCEL = re.compile(r"\b(wo|not|without)\s+[\w-]+(\s+and\s+[\w-]+)?")
_cache = {}


def _own(code):
    """The categories of one NEVO entry, leaving out what its recipe adds."""
    row = D.NEVO.get(code)
    if row is None:
        return set()
    name = _CANCEL.sub(" ", row["Engelse naam/Food name"].lower())
    group = row["Food group"]
    out = set()
    if group == "Nuts and seeds":
        out.add("seeds" if BY_NAME["seeds"][0].search(name) else "fruit" if "coconut" in name else "nuts")
    elif group == "Cereal products and types of flour" and any(n in name for n in NOT_GRAIN):
        out.add(next(c for n, c in NOT_GRAIN.items() if n in name))
    elif group in BY_NEVO_GROUP:
        out.add(BY_NEVO_GROUP[group])
    for cat, (has, unless) in BY_NAME.items():
        if has.search(name) and not (unless and unless.search(name)) and (cat != "legumes" or group != "Vegetables"):
            out.add(cat)
    return out


def of_code(code):
    """All categories of a NEVO entry, with the ones its ingredients pass on."""
    if code not in _cache:
        _cache[code] = set()                 # guards against a recipe that loops
        out = _own(code)
        recipe = D.REC.get(code, ())
        if AVERAGE.search(D.NEVO[code]["Engelse naam/Food name"]) if code in D.NEVO else False:
            # One kind of beef in nine is a meatball with egg; that doesn't put egg in "beef". Count what most of it has.
            for cat in FOLLOWS_INGREDIENTS:
                if sum(share for ing, share in recipe if cat in of_code(ing)) >= 0.5:
                    out.add(cat)
        else:
            for ing, _share in recipe:
                out |= of_code(ing) & FOLLOWS_INGREDIENTS
        _cache[code] = out
    return _cache[code]


_foods = list(csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t"))
FOOD_CATS = {f["key"]: of_code(f["nevo"]) | (of_code(f["nevo_cooked"]) if f["nevo_cooked"] else set()) for f in _foods}
FOOD_CATS["vitD_tablet"] = {"supplements"}


def members(cats):
    """The foods that any of these categories removes."""
    cats = set(cats)
    return {k for k, c in FOOD_CATS.items() if c & cats}


def removed_by(cats):
    """{food: 'nuts, spreads and salads'}: which of these ticks remove each food."""
    return {k: ", ".join(LABEL[c] for c, *_ in CATEGORIES if c in cats and c in have)
            for k, have in FOOD_CATS.items() if have & set(cats)}


def dish_blocked(code, cats):
    """Does this ticked category keep the NEVO dish off the table? Only what follows ingredients can."""
    return bool(of_code(code) & set(cats) & FOLLOWS_INGREDIENTS)


def basics_in_dinners(cats):
    """Foods removed as such whose small amounts in dinners stay: those in a ticked category that doesn't follow ingredients."""
    return members(set(cats) - FOLLOWS_INGREDIENTS) - members(set(cats) & FOLLOWS_INGREDIENTS)
