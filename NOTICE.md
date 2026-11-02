# Data and third-party notices

The MIT licence in `LICENSE` covers this project's code. It does not cover the data below, which keeps its own terms.

## NEVO (RIVM)

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

The NEVO dataset is the copyright of RIVM and the Kingdom of the Netherlands, and isn't included here. Get it from RIVM:
https://www.rivm.nl/en/dutch-food-composition-database/nevo-online-request-dataset

The tables in `data/` refer to NEVO foods by code and name. Under RIVM's conditions, NEVO data may only be used unchanged,
outputs must carry the reference line above, and users can't be charged for it. Suspicious values are handled by model
rules in the code, never by editing the data. This project isn't affiliated with or endorsed by RIVM.

## Amino acids (USDA)

`data/amino_foods.tsv` and `data/amino_families.tsv` are derived from USDA FoodData Central, SR Legacy, which is in the
public domain.

## Supermarket prices (Checkjebon)

`data/auto_prices.tsv`, `data/catalog_prices.tsv` and `data/prices.tsv` are derived from Checkjebon
(https://github.com/supermarkt/checkjebon), snapshot of 2026-10-30. Products and prices come from Dutch supermarkets,
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
