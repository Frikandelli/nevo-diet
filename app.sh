#!/usr/bin/env bash
# Start the nevo-diet app on http://localhost:8501 (Streamlit, via shell.nix).
cd "$(dirname "$0")" && exec nix-shell --run "python3 setup_data.py; streamlit run app.py --server.headless true --server.address localhost --browser.gatherUsageStats false --client.toolbarMode minimal $*"
