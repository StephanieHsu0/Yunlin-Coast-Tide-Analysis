# Yunlin Coast Tide Project

Sea-Level Trend and Extreme High-Water Risk Analysis along the Yunlin Coast: A Comparison between Mailiao and Boziliao Tide Stations

雲林沿海海平面變化與極端高潮位風險分析：以麥寮與泊子寮潮位站為例

## Project Goal

This project analyzes long-term relative sea-level variation and extreme high-water risk along the low-lying Yunlin coast using CWA tide gauge statistics. The workflow follows the Advanced Hydrology final project guideline:

- problem-driven hydrologic and engineering analysis
- exploratory analysis of data characteristics
- justified trend and extreme-value methods
- model validation and uncertainty discussion
- engineering interpretation for coastal flood risk and drainage management

## Folder Structure

```text
高水期末project/
├── data/
│   ├── raw/                  # Put original CWA files here
│   └── processed/            # Generated cleaned and annual data
├── outputs/
│   ├── figures/              # Generated figures
│   └── tables/               # Generated CSV result tables
├── scripts/
│   └── analyze_tides.py      # Main reproducible analysis script
├── slides/
│   └── presentation_draft.md # 15-17 slide draft and speaking notes
├── requirements.txt
└── README.md
```

## Required Raw Data

Place the CWA tide statistics files in `data/raw/`.

The script accepts `.csv`, `.xlsx`, and `.xls` files. Each row should represent one station-month observation or contain equivalent monthly tide statistics.

Minimum required information:

| Concept | Accepted examples |
| --- | --- |
| Station | `station`, `測站`, `站名`, filename containing `麥寮`, `Mailiao`, `泊子寮`, or `Boziliao` |
| Year | `year`, `年份`, `年` |
| Month | `month`, `月份`, `月` |
| Monthly mean tide | `mean_tide`, `平均潮位`, `月平均潮位` |
| Maximum high water | `max_high_water`, `最高高潮位`, `最高高潮暴潮位`, `最高水位` |

Optional but useful fields:

- `最高天文潮`
- `最低低潮位`
- tide datum, especially TWVD2001
- unit, preferably meters
- station longitude and latitude

## Install and Run

```powershell
cd "C:\Users\steph\Desktop\高水期末project"
python -m pip install -r requirements.txt
python scripts/analyze_tides.py
```

If no raw data is found, the script writes a template file to `data/raw/tide_data_template.csv`.

## Main Outputs

Processed data:

- `data/processed/monthly_tide_clean.csv`
- `data/processed/annual_mean_sea_level.csv`
- `data/processed/annual_max_high_water.csv`
- `data/processed/data_quality_summary.csv`

Tables:

- `outputs/tables/trend_results.csv`
- `outputs/tables/extreme_value_parameters.csv`
- `outputs/tables/model_fit_metrics.csv`
- `outputs/tables/return_levels.csv`
- `outputs/tables/sensitivity_extreme_year.csv`
- `outputs/tables/sensitivity_data_length.csv`

Figures:

- monthly mean tide time series
- monthly tide boxplot
- annual mean sea level trend
- annual maximum high-water time series
- histogram with Gumbel and GEV fitted PDFs
- Q-Q plots
- return level plots
- uncertainty and sensitivity plots

## Method Summary

1. Clean CWA monthly tide statistics into long format.
2. Compute annual mean sea level from monthly mean tide.
3. Compute annual maximum high-water level from monthly maximum high water.
4. Analyze seasonality using monthly time series and month-based distributions.
5. Estimate long-term relative sea-level trends using linear regression, Mann-Kendall test, and Sen's slope.
6. Fit Gumbel and GEV distributions to annual maximum high-water levels.
7. Compare fitted distributions using AIC, BIC, Q-Q plots, and return level reasonableness.
8. Estimate 10-, 20-, 50-, and 100-year return levels.
9. Discuss uncertainty from distribution choice, short record length, missing data, and influential extreme years.

## Interpretation Notes

- Tide-gauge trends should be interpreted as relative sea-level change, not directly as global sea-level rise.
- If the available record is about 20 years, 50- and 100-year return levels are extrapolated model estimates with substantial uncertainty.
- Observed high-water levels may include astronomical tide, surge, pressure effects, wind setup, and other meteorological influences.
- With two stations, the analysis supports a Yunlin coastal station comparison but not a full geostatistical spatial analysis.
