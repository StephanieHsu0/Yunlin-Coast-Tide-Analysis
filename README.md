# Yunlin Coast Tide Project

Sea-Level Trend and Extreme High-Water Risk Analysis along the Yunlin Coast: A Comparison between Mailiao and Boziliao Tide Stations

雲林沿海海平面變化與極端高潮位風險分析：以麥寮與萡子寮潮位站為例

## Project Goal

This Advanced Hydrology final project analyzes long-term relative sea-level variation and extreme high-water risk along the low-lying Yunlin coast using Central Weather Administration (CWA) tide statistics.

Target stations:

- 麥寮潮位站 Mailiao
- 萡子寮潮位站 Boziliao / Bozihlia

Data period:

- 2006-2025
- 20 years per station
- tide datum: 相對臺灣高程基準TWVD2001

## Data Source

Raw data:

- `C-B0052-001.json`
- Dataset: 潮位統計－臺灣各地歷史潮位觀測逐年月統計
- Source: 中央氣象署開放資料

Recommended location:

```text
data/raw/C-B0052-001.json
```

For convenience, the processing script also supports the current project-root location:

```text
C-B0052-001.json
```

## Important JSON Structure

The CWA file is nested:

```text
cwaopendata
└── Resources
    └── Resource
        └── Data
            └── SeaSurfaceObs
                └── Location
                    ├── Station
                    └── StationObsStatistics
                        ├── StartYear
                        ├── EndYear
                        ├── Annual
                        ├── Monthly
                        └── DataYear
```

The scripts specifically guard against two CWA summary-row issues:

- `Annual[0]` may be the 2006-2025 overall annual summary, so the script skips it when `len(Annual) == len(DataYear) + 1`.
- `Monthly[0:12]` may be the 2006-2025 overall monthly climatology summary, so the script skips it when `len(Monthly) == len(DataYear) * 12 + 12`.

The value `"-"` is converted to missing data (`NaN`), never to zero.

## Folder Structure

```text
高水期末project/
├── data/
│   ├── raw/
│   │   └── C-B0052-001.json
│   └── processed/
│       ├── station_info_yunlin_tide.csv
│       ├── annual_tide_yunlin.csv
│       └── monthly_tide_yunlin.csv
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── analysis_summary.md
├── scripts/
│   ├── 01_process_cwa_tide_json.py
│   ├── 02_analyze_yunlin_tides.py
├── archive/
│   ├── analyze_tides.py
│   └── tide_data_template.csv
├── slides/
│   └── presentation_draft.md
├── requirements.txt
└── README.md
```

`archive/` keeps older files for reference only. The recommended workflow is the two-script workflow below.

## Install and Run

```powershell
cd "C:\Users\steph\Desktop\高水期末project"
python -m pip install -r requirements.txt
python scripts/01_process_cwa_tide_json.py
python scripts/02_analyze_yunlin_tides.py
```

## Script 1: Process CWA JSON

Command:

```powershell
python scripts/01_process_cwa_tide_json.py
```

Input:

- `data/raw/C-B0052-001.json`

Outputs:

- `data/processed/station_info_yunlin_tide.csv`
- `data/processed/annual_tide_yunlin.csv`
- `data/processed/monthly_tide_yunlin.csv`

Expected row counts:

- `station_info_yunlin_tide.csv`: 2 rows
- `annual_tide_yunlin.csv`: 40 rows
- `monthly_tide_yunlin.csv`: 480 rows

Key derived field:

```text
hhw_minus_hat = highest_high_water_level - highest_astronomical_tide
```

## Script 2: Analyze Processed Data

Command:

```powershell
python scripts/02_analyze_yunlin_tides.py
```

Inputs:

- `data/processed/annual_tide_yunlin.csv`
- `data/processed/monthly_tide_yunlin.csv`

Figure outputs:

- `outputs/figures/01_monthly_mean_tide_timeseries_raw.png`
- `outputs/figures/02_monthly_tide_boxplot_raw.png`
- `outputs/figures/03_annual_mean_sea_level_trend.png`
- `outputs/figures/04_annual_max_high_water_timeseries.png`
- `outputs/figures/05_histogram_fitted_pdf_mailiao.png`
- `outputs/figures/06_histogram_fitted_pdf_boziliao.png`
- `outputs/figures/07_qq_plot_mailiao.png`
- `outputs/figures/08_qq_plot_boziliao.png`
- `outputs/figures/09_return_level_plot_mailiao.png`
- `outputs/figures/10_return_level_plot_boziliao.png`
- `outputs/figures/11_hhw_minus_hat_timeseries.png`
- `outputs/figures/12_monthly_mean_tide_outliers_marked.png`
- `outputs/figures/13_return_level_plot_mailiao_logx.png`
- `outputs/figures/14_return_level_plot_boziliao_logx.png`
- `outputs/figures/15_monthly_mean_tide_timeseries_qc.png`
- `outputs/figures/16_monthly_tide_boxplot_qc.png`

Table outputs:

- `outputs/tables/trend_results.csv`
- `outputs/tables/extreme_value_parameters.csv`
- `outputs/tables/model_fit_metrics.csv`
- `outputs/tables/return_levels.csv`
- `outputs/tables/sensitivity_extreme_year.csv`
- `outputs/tables/sensitivity_data_length.csv`
- `outputs/tables/monthly_outliers.csv`
- `outputs/tables/incomplete_monthly_records.csv`
- `outputs/tables/annual_outliers.csv`
- `outputs/tables/top_extreme_years.csv`
- `outputs/tables/mailiao_2018_monthly_check.csv`
- `outputs/tables/summary_statistics.csv`

Summary:

- `outputs/analysis_summary.md`

## Analysis Methods

EDA:

- raw monthly mean tide time series and raw monthly tide boxplot show all original monthly records
- QC-filtered monthly mean tide and seasonality figures exclude flagged incomplete monthly records
- annual maximum high-water time series
- annual `hhw_minus_hat` time series for preliminary interpretation of observed high water relative to astronomical tide
- IQR outlier checks for monthly `mean_tide_level` and annual `highest_high_water_level`
- top five annual extreme high-water years per station
- Mailiao 2018 monthly check sorted by monthly highest high-water level
- descriptive statistics for annual `mean_tide_level` and `highest_high_water_level`

Trend analysis:

- linear regression
- Mann-Kendall test
- Sen's slope
- slope conversion from m/year to mm/year

Extreme-value analysis:

- annual maximum series from `highest_high_water_level`
- Gumbel distribution
- GEV distribution
- histogram + fitted PDF
- Q-Q plot using Weibull plotting position
- AIC and BIC
- return levels for 10, 20, 50, and 100 years
- supplemental log-scale return level plots

Uncertainty analysis:

- remove-largest-year sensitivity for 50- and 100-year return levels
- data-length sensitivity using all years, last 15 years, and last 10 years

Data-quality figure usage:

- Raw figures show all original monthly records.
- QC-filtered figures exclude flagged incomplete monthly records.
- Annual maximum high-water analysis still uses the original `annual_tide` records.

## Interpretation Notes

- Trends should be described as relative sea-level change because tide-gauge records may reflect datum effects, land subsidence, harbor conditions, and regional ocean changes.
- A 20-year record can produce model-based 50- and 100-year return levels, but those estimates have high uncertainty.
- Annual maximum high-water level includes astronomical tide and meteorological effects. It should not be described as pure storm surge unless surge is separated.
- The two stations support a Yunlin coastal comparison but do not fully represent the entire Yunlin coastline.
- GEV is more flexible than Gumbel, but the GEV shape parameter may be unstable with only 20 annual maxima.
