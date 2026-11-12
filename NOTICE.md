# Data and third-party notices

The MIT licence in `LICENSE` covers this project's code. It does not cover the data below, which keeps its own terms.

## NEVO (RIVM)

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

The NEVO dataset is the copyright of RIVM and the Kingdom of the Netherlands, and isn't included here. Get it from RIVM:
https://www.rivm.nl/en/dutch-food-composition-database/nevo-online-request-dataset

The tables in `data/` refer to NEVO foods by code and name. Under RIVM's conditions, NEVO data may only be used unchanged,
outputs must carry the reference line above, and users can't be charged for it. Suspicious values are handled by model
rules in the code, never by editing the data. This project isn't affiliated with or endorsed by RIVM.

## Amino acids and cooking losses (USDA)

`data/amino_foods.tsv` and `data/amino_families.tsv` are derived from USDA FoodData Central, SR Legacy, and
`data/retention.tsv` from the USDA Table of Nutrient Retention Factors, Release 6 (2007). Both are in the public domain.

## Supplements

`data/supplements.tsv` lists the amounts on supplement labels, copied by hand from the product pages of PLUS, De Online
Drogist and Vitaminstore (each row has its source and date), or taken from the dose in a product's name.
`data/supplement_prices.tsv` has their prices: supermarket ones from Checkjebon (below), drugstore ones copied from the
shop's website on the date shown. Product and brand names belong to their owners; this project isn't affiliated with any
of these shops or brands, and labels and prices change.

## Supermarket prices (Checkjebon)

`data/auto_prices.tsv`, `data/catalog_prices.tsv`, `data/prices.tsv` and the supermarket rows of
`data/supplement_prices.tsv` are derived from Checkjebon (https://github.com/supermarkt/checkjebon), snapshots of
2026-10-30 (foods) and 2026-11-09 (supplements). Products and prices come from Dutch supermarkets,
change often, and may be wrong. This project isn't affiliated with any of them. Checkjebon's licence:

```
MIT License

Copyright (c) 2022 supermarkt

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
