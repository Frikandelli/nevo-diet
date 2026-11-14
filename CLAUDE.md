# nevo-diet (public release)

Claude is the sole maintainer (standard: ~/claude-workspace/claude-home/REPO-STANDARD.md).
The cheapest diet that meets every Dutch nutrient norm: a linear program on NEVO 2025 and real
supermarket prices, with a local Streamlit app. **This repo is public.**

## Read first

- Development happens in the private repo Frikandelli/nevo-diet-private (its `CLAUDE.md` and
  `PLAN.md` hold the rules and every decision). This repo is the public release of it, without
  the NEVO data files, which only RIVM may hand out (`NOTICE.md`).
- Here: `README.md` (users), `DESIGN.md` (how the model and app work), `SOURCES.md` (where the
  limits come from), `FINDINGS.md`.

## Run

`./app.sh` (Nix; http://localhost:8501). Without Nix: the venv steps in `README.md`. The app asks
for the NEVO zip on first start.

## Test

`nix-shell --run 'python3 test_app.py'` (needs the NEVO data in `data/nevo/`, which is gitignored).

## Ship

Tests green → commit → push to `main`. How changes from nevo-diet-private get here isn't written
down yet (card on the board); until it is, change this repo only for fixes to the release itself.

## Ask the owner first

- Anything that adds data files, or that touches the licence or the notices (`LICENSE`, `NOTICE.md`).
- Never: the NEVO files, anyone's profile or body data, private paths or notes. This repo is public.

## Keep current

`README.md` with what the app does; `DESIGN.md` when the model changes; `NOTICE.md` when a data
source is added.
