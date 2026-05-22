# Presentation Draft

Project title:

Sea-Level Trend and Extreme High-Water Risk Analysis along the Yunlin Coast: A Comparison between Mailiao and Boziliao Tide Stations

雲林沿海海平面變化與極端高潮位風險分析：以麥寮與泊子寮潮位站為例

Target length: 15-17 slides, about 12 minutes plus 1-3 minutes Q&A.

## Slide 1. Title

Content:

- English and Chinese title
- Course: Advanced Hydrology
- Team members
- Date

Speaking point:

This project investigates long-term relative sea-level variation and extreme high-water risk along the Yunlin coast using CWA tide-gauge data.

## Slide 2. Motivation

Content:

- Yunlin coast is low-lying and sensitive to high tide, storm surge, drainage backwater, and possible land subsidence.
- Higher background sea level can increase coastal flood and drainage risk.
- Extreme high-water levels are relevant to seawalls, tide gates, pumping stations, and coastal management.

Suggested visual:

- Yunlin coast photo or location map.

## Slide 3. Research Questions

Content:

1. Do Mailiao and Boziliao show long-term relative sea-level trends?
2. Is there clear seasonality in monthly mean tide level?
3. Are annual maximum high-water levels different between the two stations?
4. Can Gumbel or GEV distributions describe annual maximum high-water levels?
5. What are the 10-, 20-, 50-, and 100-year return levels?
6. What do the results imply for coastal risk and engineering management?

## Slide 4. Study Area and Stations

Content:

- Study area: Yunlin coast, western Taiwan.
- Stations: Mailiao and Boziliao tide gauges.
- Mailiao: represents northern Yunlin coast and industrial/harbor setting.
- Boziliao: comparison station for another Yunlin coastal location.

Suggested visual:

- Station location map.
- Table with station name, latitude, longitude, data period, tide datum.

## Slide 5. Data Source and Variables

Content:

- Source: Central Weather Administration tide statistics.
- Core variables:
  - monthly mean tide level
  - annual mean sea level derived from monthly mean tide
  - annual maximum high-water level derived from monthly maxima
- Tide datum should be checked, ideally TWVD2001.

Suggested table:

- `outputs/tables` and `data/processed/data_quality_summary.csv` after running analysis.

## Slide 6. Data Processing

Content:

- Clean station-month records into long format.
- Compute annual mean sea level only when at least 10 valid months are available.
- Compute annual maximum high-water level from monthly maximum high-water data.
- Flag years with missing months because annual maxima may be underestimated if extreme months are missing.

Suggested visual:

- Simple workflow diagram or data-quality table.

## Slide 7. Monthly Mean Tide Time Series

Content:

- Compare monthly mean tide changes through time for both stations.
- Identify whether stations vary synchronously.
- Note unusual months or periods.

Figure:

- `outputs/figures/01_monthly_mean_tide_timeseries.png`

## Slide 8. Seasonality

Content:

- Compare monthly distributions using boxplots.
- Identify months with higher background tide levels.
- Discuss whether high-tide season overlaps with typhoon or monsoon-related risk periods.

Figure:

- `outputs/figures/02_monthly_tide_boxplot.png`

## Slide 9. Trend Analysis Method

Content:

- Linear regression estimates the mean rate of annual sea-level change.
- Mann-Kendall test checks monotonic trend without assuming normality.
- Sen's slope provides a robust nonparametric trend estimate.

Equation:

`SL_t = beta_0 + beta_1 t + epsilon_t`

Interpretation:

- `beta_1` in m/year is converted to mm/year.
- Results are relative sea-level changes measured at tide gauges.

## Slide 10. Trend Analysis Results

Content:

- Present annual mean sea level with trend lines.
- Report slope, p-value, R-squared, MK p-value, and Sen's slope.
- Compare whether two stations show consistent trends.

Figures and tables:

- `outputs/figures/05_annual_mean_trend.png`
- `outputs/tables/trend_results.csv`

## Slide 11. Extreme-Value Analysis Method

Content:

- Use annual maximum series because the target is each year's most severe observed high-water event.
- Fit Gumbel and GEV distributions.
- Gumbel is simpler and stable.
- GEV is more flexible but the shape parameter can be unstable with short records.

Key limitation:

- If the record is about 20 years, high return-period estimates are extrapolations with high uncertainty.

## Slide 12. Distribution Fitting

Content:

- Compare histogram and fitted PDFs.
- Use AIC and BIC for model comparison.
- Do not select a model from AIC/BIC alone; also inspect tail behavior and engineering reasonableness.

Figures and tables:

- `outputs/figures/06_mailiao_histogram_fitted_pdf.png`
- `outputs/figures/06_boziliao_histogram_fitted_pdf.png`
- `outputs/tables/model_fit_metrics.csv`
- `outputs/tables/extreme_value_parameters.csv`

## Slide 13. Model Validation with Q-Q Plots

Content:

- Q-Q plots compare observed annual maxima with theoretical quantiles.
- Points close to the 45-degree line indicate reasonable fitting.
- Tail deviations imply uncertainty in extreme return levels.

Figures:

- `outputs/figures/07_mailiao_qq_plot.png`
- `outputs/figures/07_boziliao_qq_plot.png`

## Slide 14. Return Level Results

Content:

- Present 10-, 20-, 50-, and 100-year return levels.
- Explain annual exceedance probability:
  - 10-year: 10%
  - 20-year: 5%
  - 50-year: 2%
  - 100-year: 1%
- Emphasize that a 100-year water level means 1% chance in any year, not once every exactly 100 years.

Figures and tables:

- `outputs/figures/08_mailiao_return_level.png`
- `outputs/figures/08_boziliao_return_level.png`
- `outputs/tables/return_levels.csv`

## Slide 15. Uncertainty and Sensitivity

Content:

- Distribution-choice uncertainty: Gumbel vs GEV can diverge at high return periods.
- Extreme-year sensitivity: removing the largest annual maximum tests dependence on one event.
- Data-length limitation: short records make 50- and 100-year return levels uncertain.
- Station representativeness: two stations cannot fully represent all Yunlin coastal variability.

Figures and tables:

- `outputs/figures/09_extreme_year_sensitivity.png`
- `outputs/tables/sensitivity_extreme_year.csv`
- `outputs/tables/sensitivity_data_length.csv`

## Slide 16. Engineering and Disaster-Risk Implications

Content:

- If annual mean sea level increases, the background water level becomes higher.
- The same storm surge or high-tide event may produce higher total water levels in the future.
- Higher sea level can reduce drainage efficiency through tidal backwater.
- Return levels can support preliminary discussion of seawall, tide-gate, pumping-station, and coastal flood-risk management.

Important wording:

- Use "relative sea-level change" instead of directly attributing trends to global sea-level rise.
- Use "observed high-water risk" unless tide and surge components are separated.

## Slide 17. Conclusions

Content template:

1. The monthly tide data show [seasonality pattern] and [station similarity/difference].
2. Annual mean sea level shows [increasing/decreasing/not significant] relative sea-level trend at [station].
3. Annual maximum high-water levels can be described by [Gumbel/GEV/both with limitations].
4. Return-level estimates suggest [station] has [higher/lower/similar] extreme high-water risk.
5. High return-period estimates are uncertain due to short records and distribution choice.

Future work:

- Include longer tide-gauge records if available.
- Separate astronomical tide and storm-surge components.
- Include land-subsidence data.
- Add more coastal stations for spatial interpretation.

## Backup Q&A Notes

Possible question: Why use annual maximum series?

Answer:

The target is yearly extreme high-water risk, and annual maximum series is consistent with block maxima extreme-value analysis. The limitation is that it keeps only one event per year.

Possible question: Why compare Gumbel and GEV?

Answer:

Gumbel is a stable baseline for maxima, while GEV is theoretically more general for block maxima. Comparing both shows distribution-choice uncertainty.

Possible question: Can a 20-year record estimate a 100-year return level?

Answer:

It can produce a model-based extrapolation, but uncertainty is large. We interpret the 100-year estimate as a sensitivity and risk indicator, not as a highly certain design value.

Possible question: Is the trend caused by global sea-level rise?

Answer:

Not necessarily. Tide gauges measure relative sea level, which may include land subsidence, local datum issues, harbor effects, and regional ocean changes. Therefore the project uses the term relative sea-level change.
