# Where the limits come from

Checked on 2026-11-02 against the original documents, for the limits in `data/requirements.tsv` and the profiles in
`data/profiles.tsv`. In the app, the tab "Profile & limits" shows each limit with its source and link.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

## The short version

- **Most limits are confirmed.** Vitamins, minerals, upper limits and amino acids match the current tables.
- **The model follows the newest Dutch advice.** On 7 July 2026 the Gezondheidsraad replaced its 2001 norms for fats,
  carbohydrates and fibre (no. 2026/14). These are in the model, and so is EFSA's iron absorption for women.
- **A few limits are project choices,** stricter or different from the Dutch norm on purpose. They are listed below.

## Changed on 2026-11-02

Cost per day for the cheapest diet at AH, changing only that limit from the earlier values.

| Limit | Before | Now | Effect |
|---|---|---|---|
| Linoleic acid | ≥ 2 en% | ≥ 4 en% | none, it was already above 4 |
| ALA | ≥ 1 en% | ≥ 0.5 en% | €0.01-0.02 cheaper |
| Carbohydrates | ≥ 40 en% | no number | none |
| Fibre | ≥ 3.4 g/MJ | ≥ 3.0 g/MJ, the low end of the 3.0-3.5 range | part of the package below |
| Iron, women 18-49 | 16 mg × 16% = 2.56 mg absorbed | 16 mg × 18% = 2.88 mg absorbed | €0.10 more |

## Where the model deliberately differs

| Limit | In the model | What the evidence says | Cost of following it |
|---|---|---|---|
| Sodium | ≤ 2400 mg (6 g salt, Dutch) | WHO and EFSA 2019: 2000 mg | up to €0.01 more |
| Trans fat | ≤ 1 en% as a working maximum | As low as possible, no number (2026/14) | not tested |
| Saturated fat, free sugars | ≤ 10 en% | As low as possible, with 10 en% as the intermediate step (2026/14) | not tested |
| Phosphorus, vitamin E | Hard minimums | Voedingscentrum: too little data, "not meant as a target" | no change |
| Zinc | 14.0 / 11.0 mg (EFSA, high phytate) | Dutch norm 9.0 / 7.0 mg | no change |

## Every limit

| Limit | Source | Status |
|---|---|---|
| energy | [Profile energy, with a project band of +4%. Dutch average needs: Gezondheidsraad 2022/19](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2022/08/16/advies-voedingsnormen-voor-energie/Advies_Voedingsnormen-voor-energie.pdf) | project choice |
| protein | [Profile g/kg x weight. Dutch norm for adults 0.83 g/kg: Gezondheidsraad 2021/10](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2021/03/02/voedingsnormen-voor-eiwitten/Advies-Voedingsnormen-voor-eiwitten-referentiewaarden-voor-de-inname-van-eiwitten.pdf) | confirmed |
| fibre | [Gezondheidsraad 2026/14: recommended range 3.0-3.5 g/MJ (2006: 3.4). The model uses the low end as its minimum](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| carbs | [Gezondheidsraad 2026/14 gives no number (2001: at least 40 en%): mainly wholegrain, vegetables, fruit, pulses, dairy](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| fat | [Gezondheidsraad 2026/14: 20-40 en%, unchanged from 2001](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| satfat | [Gezondheidsraad 2026/14: as low as possible, with 10 en% as an intermediate step](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| trans | [Gezondheidsraad 2026/14: as low as possible, no number. The model keeps 1 en% (the 2001 limit) as a working maximum](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | project choice |
| linoleic | [Gezondheidsraad 2026/14: AI 4 en% (was 2 en% since 2001)](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| ala | [Gezondheidsraad 2026/14: AI 0.5 en% (was 1 en% since 2001)](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| epa_dha | [Gezondheidsraad 2026/14: AI 200 mg/day for adults, unchanged](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf) | confirmed |
| sodium | [Gezondheidsraad 2015/24 and 2025/19: at most 6 g salt. WHO and EFSA 2019 use 2000 mg sodium](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2015/11/04/richtlijnen-goede-voeding-2015/201524_Richtlijnen+goede+voeding+2015.pdf) | newer advice differs |
| potassium | [Voedingscentrum 2025: AI 3500 mg, adults](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| calcium | [Voedingscentrum 2025: 950 mg at 25-69 (18-24: 1000; women 50-69: 1100; from 70: 1200). Upper limit 2500: EFSA 2012](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| phosphorus | [Voedingscentrum 2025: AI 550 mg, listed as too little data for a good norm and not meant as a target](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | not a firm target |
| magnesium | [Voedingscentrum 2025: AI men 350, women 300 mg](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| iron_abs | [Voedingscentrum 2025 iron (men 11, women 18-49 16 mg) x EFSA 2015 absorption (men 16%, premenopausal women 18%). Haem 25% and non-haem 10% are a model rule](https://www.efsa.europa.eu/en/efsajournal/pub/4254) | project choice |
| iron | [EFSA 2024: safe level 40 mg, not a formal upper limit. Taken over by Voedingscentrum 2025](https://www.efsa.europa.eu/sites/default/files/2024-05/ul-summary-report.pdf) | confirmed |
| zinc | [EFSA 2014 at 900 mg/day phytate: men 14.0, women 11.0 mg, chosen for this diet. The Dutch norm is lower: men 9.0, women 7.0 (Voedingscentrum 2025). Upper limit 25: EFSA](https://www.efsa.europa.eu/sites/default/files/2017_09_DRVs_summary_report.pdf) | project choice |
| copper | [Voedingscentrum 2025: 0.9 mg. Upper limit 5 mg: EFSA. EFSA 2023 also has an ADI of 0.07 mg/kg, 4.4 mg at 62.5 kg](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| iodine | [Voedingscentrum 2025: AI 150 µg. Upper limit 600 µg: EFSA](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| selenium | [Voedingscentrum 2025: AI 70 µg. Upper limit 255 µg: EFSA 2023. Gezondheidsraad 2024 revised how this norm is qualified, not the number](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| vitA | [Voedingscentrum 2025: ADH men 800, women 690 µg RAE](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| retinol | [EFSA 2024: upper limit 3000 µg preformed vitamin A](https://www.efsa.europa.eu/sites/default/files/2024-05/ul-summary-report.pdf) | confirmed |
| thiamin | [Voedingscentrum 2025: ADH 0.1 mg/MJ](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| riboflavin | [Voedingscentrum 2025: 1.6 mg at 18-69](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| niacin | [Voedingscentrum 2025: ADH 1.6 mg NE/MJ](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| vitB6 | [Voedingscentrum 2025: 1.5 mg (men from 51: 1.8). Upper limit 12 mg: EFSA 2023](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| folate | [Voedingscentrum 2025: 300 µg DFE](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| folic_acid | [EFSA 2023: upper limit 1000 µg, for added folic acid and similar forms only](https://www.efsa.europa.eu/sites/default/files/2024-05/ul-summary-report.pdf) | confirmed |
| vitB12 | [Voedingscentrum 2025: 2.8 µg](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| vitC | [Voedingscentrum 2025: 75 mg](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| vitD | [Voedingscentrum 2025: 10 µg at 18-69 (from 70: 20). Upper limit 100 µg: EFSA 2023](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| vitE | [Voedingscentrum 2025: AI men 13, women 11 mg, listed as too little data for a good norm and not meant as a target. Upper limit 300 mg: EFSA, under review](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | not a firm target |
| vitK1 | [Voedingscentrum 2025: AI 70 µg](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf) | confirmed |
| histidine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 10 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| isoleucine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 20 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| leucine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 39 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| lysine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 30 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| met_cys | [WHO/FAO/UNU 2007 (TRS 935), table 23: 15 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| phe_tyr | [WHO/FAO/UNU 2007 (TRS 935), table 23: 25 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| threonine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 15 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| tryptophan | [WHO/FAO/UNU 2007 (TRS 935), table 23: 4 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| valine | [WHO/FAO/UNU 2007 (TRS 935), table 23: 26 mg/kg/day](https://iris.who.int/handle/10665/43411) | confirmed |
| free_sugars | [WHO 2015: below 10 en% (strong), below 5 en% (conditional). Gezondheidsraad 2026/14: as low as possible, with 10 en% as an intermediate step](https://www.who.int/news/item/04-03-2015-who-calls-on-countries-to-reduce-sugars-intake-among-adults-and-children) | confirmed |

## The profiles

| Profile | Value | Evidence |
|---|---|---|
| Average man, woman | Height 182.6 and 168.5 cm | Exact match: [CBS 81565NED](https://opendata.cbs.nl/ODataApi/odata/81565NED), ages 30-40, 2025. Self-reported, margin ±0.3 cm |
| Average man, woman | Weight 73.4 and 62.5 kg (BMI 22) | The healthy reference used by [Gezondheidsraad 2021/10](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2021/03/02/voedingsnormen-voor-eiwitten/Advies-Voedingsnormen-voor-eiwitten-referentiewaarden-voor-de-inname-van-eiwitten.pdf) (73.1 and 63.1 kg). Not what people weigh: CBS reports 85.7 and 71.9 kg |
| Average man, woman | 2743 and 2165 kcal (Schofield × PAL 1.6) | [Gezondheidsraad 2022/19](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2022/08/16/advies-voedingsnormen-voor-energie/Advies_Voedingsnormen-voor-energie.pdf), ages 30-39: 2690 and 2170 kcal, using Henry. Man 2% above, woman equal |
| Average man, woman | Protein 0.83 g/kg | Exact match: Gezondheidsraad 2021/10, taken from EFSA |
| Active man, woman | PAL 1.9 | Between active (1.8) and very active (2.0) in 2022/19. A project choice, not a published level |
| Active man, woman | Protein 1.2 g/kg | A project choice, above the norm and below the ISSN 2017 range of 1.4-2.0 for people who train |

**Energy estimate for changed bodies and new profiles:** Henry (2005), the equation behind the Dutch norms, with
coefficients from table A1 of the [2022/19 background document](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2022/08/16/achtergronddocument-evaluation-of-dietary-reference-values-for-energy/Background-document_+DRVs-for-energy.pdf).
It reproduces all six adult reference values tested from 2022/19 to the kcal (men 1781, 1683, 1535; women 1441, 1354, 1243).

**Limits that change with age** are not automatic. Voedingscentrum 2025: vitamin D 20 µg and calcium 1200 mg from 70,
vitamin B6 1.8 mg for men from 51, and for women iron 11 mg and calcium 1100 mg from 50. Calcium is 1000 mg at 18-24, so the
model's 950 mg is slightly low for that group. The app warns about the older ages for profiles from 50.

**Protein for people who train:** [Morton 2018](https://pubmed.ncbi.nlm.nih.gov/28698222/) finds gains level off near 1.62 g/kg (95% CI 1.03-2.20, p = 0.079, so not a sharp line), inside the [ISSN 2017](https://pubmed.ncbi.nlm.nih.gov/28642676/) range of 1.4-2.0. Use the protein box or your own profile to try this.

## What could not be confirmed

- **Schofield's weight-only coefficients** in `profiles.py` were not found printed in a primary source. They only affect
  the standard profiles without their own calories.
- **ACSM/Academy of Nutrition and Dietetics 2016, protein 1.2-2.0 g/kg:** seen only in a secondary source; the
  [abstract](https://pubmed.ncbi.nlm.nih.gov/26891166/) has no number. So it is not used above.
- **Gezondheidsraad 2018/19 and 2001/19** were not read directly. Their values come through Voedingscentrum 2025 and the 2026 advice.
- **EFSA's zinc 14.0 mg for men:** the men's range of 9.4-16.3 mg and the women's 11.0 mg were read in the
  [summary report](https://www.efsa.europa.eu/sites/default/files/2017_09_DRVs_summary_report.pdf); the men's value at 900 mg
  phytate was not legible in the extracted table.
- **Copper:** the 5 mg upper limit is confirmed, but EFSA 2023 also set an intake of 0.07 mg/kg, which is below 5 mg for anyone under 71 kg.

## Main documents

- Voedingscentrum, [Aanbevelingen voor vitamines, mineralen en spoorelementen](https://mobiel.voedingscentrum.nl/Assets/Uploads/voedingscentrum/Documents/Professionals/vitamines%20en%20mineralen/Vitamines%20mineralen%20en%20spoorelementen_2025_def.pdf), May 2025
- Gezondheidsraad, [Voedingsnormen voor vetten, vetzuren, verteerbare koolhydraten en voedingsvezels](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2026/07/07/advies-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels/14-voedingsnormen-voor-vetten-vetzuren-verteerbare-koolhydraten-en-voedingsvezels-erratum.pdf), no. 2026/14, and [Voedingscentrum's summary](https://www.voedingscentrum.nl/nl/nieuws/nieuwe-aanbevelingen-vetten-koolhydraten-vezels.aspx)
- Gezondheidsraad, [Richtlijnen goede voeding 2015](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2015/11/04/richtlijnen-goede-voeding-2015/201524_Richtlijnen+goede+voeding+2015.pdf), no. 2015/24, and [2025](https://www.gezondheidsraad.nl/site/binaries/site-content/collections/documents/2025/12/04/advies-richtlijnen-goede-voeding-eiwitbronnen-en-voedingspatronen-2025/19-richtlijnen-goede-voeding-eiwitbronnen-en-voedingspatronen-2025-advies.pdf), no. 2025/19
- EFSA, [Overview on Tolerable Upper Intake Levels](https://www.efsa.europa.eu/sites/default/files/2024-05/ul-summary-report.pdf), version 11, August 2025, adopted for the Netherlands by Gezondheidsraad 2023/04
- EFSA, [Dietary Reference Values for iron](https://www.efsa.europa.eu/en/efsajournal/pub/4254), 2015
- WHO, [sodium](https://www.who.int/news-room/fact-sheets/detail/sodium-reduction), [free sugars](https://www.who.int/news/item/04-03-2015-who-calls-on-countries-to-reduce-sugars-intake-among-adults-and-children), [amino acids, TRS 935](https://iris.who.int/handle/10665/43411)
