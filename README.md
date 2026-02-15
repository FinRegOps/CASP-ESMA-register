[README.md](https://github.com/user-attachments/files/25327737/README.md)
# CASP Dashboard

Interactive dashboard visualising the ESMA Register of Crypto-Asset Service Providers (CASPs) under MiCAR.

## How it works

1. `generate.py` downloads the latest CASP CSV from [ESMA's MiCA register](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/markets-crypto-assets-regulation-mica)
2. It parses the data and generates a self-contained `index.html` dashboard (pure HTML/CSS/JS, no dependencies)
3. GitHub Pages serves the dashboard at your repo URL

## Automatic updates

A GitHub Action runs every Monday at 08:00 UTC:
- Downloads the latest CSV from ESMA
- Regenerates the dashboard
- Commits and pushes only if data has changed

You can also trigger it manually: **Actions** → **Update CASP Dashboard** → **Run workflow**

## Manual usage

```bash
# Generate from ESMA (downloads CSV automatically)
python generate.py

# Generate from a local CSV file
python generate.py --csv CASPS.csv

# Custom output path
python generate.py --output docs/index.html
```

## Repository structure

```
├── .github/workflows/update-dashboard.yml   # Auto-update workflow
├── generate.py                               # Dashboard generator script
├── index.html                                # Generated dashboard (served by GitHub Pages)
└── README.md
```

## Data source

[ESMA Interim MiCA Register — Crypto-asset service providers (CSV)](https://www.esma.europa.eu/sites/default/files/2024-12/CASPS.csv)

Updated weekly by ESMA. See the [ESMA MiCA page](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/markets-crypto-assets-regulation-mica) for more information.
