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
import supplements as S

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
    ("supplements", "supplements", "vitamin and mineral pills, fish and algae oil, psyllium"),
]
# Allergies and intolerances. NEVO has no allergen data, so these come from NEVO's group, name and recipes like the rest, but
# the other way round: when in doubt a food goes out. A processed food's real recipe is on its label, not in NEVO. Celery,
# mustard, lupin and sulphites aren't offered: nothing in the data would show where they're hidden.
ALLERGIES = [
    ("x_gluten", "gluten", "wheat, rye, barley, spelt and oats (usually contaminated), and what's made with them"),
    ("x_lactose", "lactose", "milk products, butter and cheese, unless labelled lactose-free"),
    ("x_milk", "milk", "every milk product, lactose-free too, and food that may hold milk"),
    ("x_egg", "egg", "eggs, mayonnaise, baked goods"),
    ("x_fish", "fish", "fish, fish paste, anchovies"),
    ("x_shellfish", "shellfish", "crustaceans and molluscs: shrimp, crab, mussels, oysters, snails"),
    ("x_peanut", "peanuts", "peanuts, peanut oil, frying oils, and food that may hold them"),
    ("x_nuts", "tree nuts", "almonds, cashews, hazelnuts, walnuts and the like, and food that may hold them; not coconut"),
    ("x_soy", "soy", "soy drinks, tofu, tempeh, margarine, chocolate, meat substitutes"),
    ("x_sesame", "sesame", "sesame, tahini, hummus, falafel, bread and food that may hold it"),
]
LABEL = {k: label for k, label, _ in CATEGORIES + ALLERGIES}
# A dinner or composite food with this as an ingredient counts as having it. The rest only cover the food itself.
ALLERGY_KEYS = {a[0] for a in ALLERGIES}
FOLLOWS_INGREDIENTS = {"meat", "fish", "eggs", "dairy", "legumes", "grain", "nuts", "seeds", "veg", "fruit", "potatoes"} | ALLERGY_KEYS

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
# Whose recipe is on the label, not in NEVO: it may hold anything these allergens are commonly used for.
_FACTORY = (r"sausage|salami|saveloy|metworst|hamburger|kromesky|forcemeat|scrapple|black pudding|\bpate\b|luncheon|processed|"
            r"corned beef|frikandel|filet americain|tartare spiced|croquette|fried|rosti|fish fingers|surimi|marinated|"
            r"schnitzel|cordon bleu|filled|ready-to-eat|\bballs?\b|rolled|beef olives|minced meat")
_FACTORY_GROUPS = {"Cold meat cuts", "Savoury snacks", "Savoury bread spreads", "Pastry and biscuits", "Sauces", "Soups",
                   "Meat substitutes and dairy substitutes"}
_NOT_FACTORY = re.compile(r"^drink |rice drink|tofu|coconut milk|peanut butter|sesame paste")      # one thing, or close to it
_BAKED = {"Bread", "Pastry and biscuits"}
_CHOC = r"chocolate|cocoa|sprinkles|\bflakes (dark|milk|white)|nougat|praline|comfits|speculaas|ice cream|tiramisu"
_CEREAL_OK = r"\brice\b(?!.*(nuts|fruit))|\bcorn\b|millet|quinoa|buckwheat|potato starch|flour (almond|coconut)|gluten free"
_MUESLI = r"muesli|breakfast cereal|granola"
# allergen -> (name has this, these NEVO groups count, a factory food counts, unless the name has that)
ALLERGENS = {
    "x_gluten": (r"wheat(?<!buckwheat)|\brye\b|barley|spelt|\boats?\b|semolina|couscous|bulgur|seitan|\bbread|crumbs|\bflour\b|"
                 r"pasta|noodle|\bbami\b|macaroni|spaghetti|gnocchi|pastry|dough|pizza|tortilla|\bwrap|pancake|poffertjes|"
                 r"vol -au|soy sauce|ketjap|tomato sauce|baked in|chilli canned|\bbeer\b|\bmalt|croutons|speculaas|comfits|liquorice|sandwich spread|" + _MUESLI,
                 _BAKED, True, r"gluten free|rice cake|corn cakes|flour (almond|coconut|corn|buckwheat)|\boil\b"),
    "x_lactose": (r"\bmilk\b|milkchocolate|cheese|\bcream\b|creme|yoghurt|yogurt|quark|custard|\bbutter\b|kefir|\bwhey\b|mascarpone|"
                  r"blancmange|pudding airy|porridge|creamer|brioche|croissant|margarine|dairy|ayran|pastry|dough|bakery mix|pancake|" + _MUESLI + "|" + _CHOC,
                  {"Milk and milk products", "Cheese", "Pastry and biscuits"}, True,
                  r"lactose.free|plant-based|coconut|\bsoya?\b|\balmond\b|peanut butter|nut butter|cocoa butter|butter bean|"
                  r"salad cream|non-dairy"),
    "x_milk": (r"\bmilk\b|milkchocolate|cheese|\bcream\b|creme|yoghurt|yogurt|quark|custard|\bbutter\b|kefir|\bwhey\b|mascarpone|"
               r"blancmange|pudding airy|porridge|creamer|margarine|dairy|ayran|lactose|pastry|dough|bakery mix|pancake|" + _MUESLI + "|" + _CHOC,
               {"Milk and milk products", "Cheese"} | _BAKED, True,
               r"plant-based|coconut|\bsoya?\b|\balmond\b|peanut butter|nut butter|cocoa butter|butter bean|non-dairy|gluten free bread"),
    "x_egg": (r"\beggs?\b|omelette|mayonnaise|\bsalad\b|pastry|pancake|poffertjes|brioche|croissant|custard|meringue|tiramisu|noodle|"
              r"\bbami\b|gnocchi|vol -au|bakery mix|blancmange|pudding airy|sandwich spread|ice cream", {"Eggs", "Pastry and biscuits"},
              True, None),
    "x_fish": (r"\bfish\b|salmon|\btuna\b|herring|mackerel|sardine|anchov|\bcod\b|trout|plaice|pollock|halibut|pangasius|tilapia|caviar|"
               r"\beel\b|surimi|sandwich spread", None, False, r"shellfish"),
    "x_shellfish": (r"shrimp|prawn|\bcrab\b|lobster|mussel|oyster|snail|squid|scallop|surimi|shellfish|crustacean", None, False, None),
    "x_peanut": (r"peanut|satay|almond|cashew|hazelnut|walnut|pecan|pistachio|macadamia|pine nut|chestnut|\bnuts?\b|seeds and kernels|frying|\bwok\b|" + _MUESLI + "|" + _CHOC, {"Pastry and biscuits"}, False, None),
    "x_nuts": (r"peanut|satay|almond|cashew|hazelnut|walnut|pecan|pistachio|macadamia|pine nut|chestnut|brazil|\bnuts?\b|seeds and kernels|marzipan|"
               r"nougat|pesto|frangipane|" + _MUESLI + "|" + _CHOC, {"Pastry and biscuits"}, False, r"water chestnut|coconut"),
    "x_soy": (r"\bsoya?\b|tofu|tempeh|plant-based|miso|ketjap|margarine|multigrain|\bwok\b|sandwich spread|coffee creamer|" + _CHOC,
              {"Meat substitutes and dairy substitutes", "Pastry and biscuits"}, True, r"^coconut milk|drink (oat|almond|coconut|rice)|rice drink"),
    "x_sesame": (r"sesame|tahin|hummus|falafel|seeds and kernels|multiseed|\bwok\b", _BAKED | {"Savoury snacks", "Savoury bread spreads"}, False,
                 r"peanut butter"),
}
ALLERGENS = {k: (re.compile(has), groups or set(), factory, re.compile(unless) if unless else None)
             for k, (has, groups, factory, unless) in ALLERGENS.items()}
_FACTORY = re.compile(_FACTORY)
_CEREAL_OK = re.compile(_CEREAL_OK)
FREE_OF = {"x_gluten": r"gluten.free", "x_lactose": r"lactose.free"}      # the label says so, whatever a typical recipe has
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
    plain = row["Engelse naam/Food name"].lower()      # "wo salt" cancels nothing here: "gluten free" must stay readable
    for key, (has, groups, factory, unless) in ALLERGENS.items():
        hit = bool(has.search(name)) or group in groups or (factory and (group in _FACTORY_GROUPS or _FACTORY.search(name)) and not _NOT_FACTORY.search(name))
        if key == "x_gluten" and group == "Cereal products and types of flour" and not _CEREAL_OK.search(name):
            hit = True
        if hit and not (unless and unless.search(plain)):
            out.add(key)
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
                if cat not in ALLERGY_KEYS and sum(share for ing, share in recipe if cat in of_code(ing)) >= 0.5:
                    out.add(cat)
            # An allergy isn't a matter of what most of it has.
            for ing, _share in recipe:
                out |= of_code(ing) & ALLERGY_KEYS
            plain = D.NEVO[code]["Engelse naam/Food name"].lower() if code in D.NEVO else ""
            out -= {key for key, words in FREE_OF.items() if re.search(words, plain)}
        else:
            for ing, _share in recipe:
                out |= of_code(ing) & FOLLOWS_INGREDIENTS
            plain = D.NEVO[code]["Engelse naam/Food name"].lower() if code in D.NEVO else ""
            out -= {key for key, words in FREE_OF.items() if re.search(words, plain)}
        _cache[code] = out
    return _cache[code]


_foods = list(csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t"))
FOOD_CATS = {f["key"]: of_code(f["nevo"]) | (of_code(f["nevo_cooked"]) if f["nevo_cooked"] else set()) for f in _foods}
FOOD_CATS.update({k: S.categories(k) for k in S.SUPP})      # fish oil: fish; a beef gelatin capsule: meat ...
# The real products count too: about 1 in 10 automatic matches is wrong ("Cranberries fresh" had a nut bar among its products),
# and a food is only as safe as whatever the cheapest product turns out to be.
_MILKY = r"(?<!pinda)kaas|boter|(?<!kokos)(?<!soja)(?<!haver)(?<!amandel)(?<!rijst)(?<!cocos)melk|(?<!kokos)(?<!cocos)room|yoghurt|kwark|lactose"
_PLANT = r"plantaardig|alpro|(soja|haver|rijst|amandel|kokos) ?drink"       # Melkan is a brand, and a plant yoghurt says "yoghurt"
PRODUCT_WORDS = {
    "x_gluten": (r"tarwe|rogge|gerst|spelt|\bhaver|gluten|brood|volkoren|(?<!aardappel)(?<!mais)(?<!rijst)meel\b|beschuit|paneer", r"glutenvrij"),
    "x_lactose": (_MILKY, _PLANT + r"|lactosevrij|lactofree"), "x_milk": (_MILKY, _PLANT),
    "x_egg": (r"\bei\b|\beieren|\beier|mayo", None),
    "x_fish": (r"\bvis\b|\bvisse|zalm|tonijn|haring|makreel|ansjovis", None),
    "x_shellfish": (r"garnal|mossel|\bkrab|kreeft|\boester", None),
    "x_peanut": (r"pinda|noot|noten|amandel|marsepein", None), "x_nuts": (r"pinda|noot|noten|amandel|marsepein", None),
    "x_soy": (r"\bsoja|tofu|tempeh", None), "x_sesame": (r"sesam|tahin|hummus", None),
}
for _r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t"):
    _p = _r["product"].lower()
    for _key, (_has, _unless) in PRODUCT_WORDS.items():
        if _r["key"] in FOOD_CATS and re.search(_has, _p) and not (_unless and re.search(_unless, _p)):
            FOOD_CATS[_r["key"]].add(_key)


def members(cats):
    """The foods that any of these categories removes."""
    cats = set(cats)
    return {k for k, c in FOOD_CATS.items() if c & cats}


def removed_by(cats):
    """{food: 'nuts, spreads and salads'}: which of these ticks remove each food."""
    return {k: ", ".join(LABEL[c] for c, *_ in CATEGORIES + ALLERGIES if c in cats and c in have)
            for k, have in FOOD_CATS.items() if have & set(cats)}


def dish_blocked(code, cats):
    """Does this ticked category keep the NEVO dish off the table? Only what follows ingredients can."""
    return bool(of_code(code) & set(cats) & FOLLOWS_INGREDIENTS)


def basics_in_dinners(cats):
    """Foods removed as such whose small amounts in dinners stay: those in a ticked category that doesn't follow ingredients."""
    return members(set(cats) - FOLLOWS_INGREDIENTS) - members(set(cats) & FOLLOWS_INGREDIENTS)
