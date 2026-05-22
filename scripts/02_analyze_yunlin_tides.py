from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"
SUMMARY_PATH = ROOT / "outputs" / "analysis_summary.md"

RETURN_PERIODS = [10, 20, 50, 100]
STATION_SLUGS = {
    "麥寮潮位站": "mailiao",
    "萡子寮潮位站": "boziliao",
}


@dataclass
class FitResult:
    station_name: str
    distribution: str
    params: tuple[float, ...]
    log_likelihood: float
    aic: float
    bic: float


def ensure_directories() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def configure_plots() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def save_fig(filename: str) -> None:
    plt.tight_layout()
    plt.savefig(FIG_DIR / filename, dpi=300, bbox_inches="tight")
    plt.close()


def load_processed_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    station_path = PROCESSED_DIR / "station_info_yunlin_tide.csv"
    annual_path = PROCESSED_DIR / "annual_tide_yunlin.csv"
    monthly_path = PROCESSED_DIR / "monthly_tide_yunlin.csv"

    missing = [path for path in [station_path, annual_path, monthly_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing processed CSV files. Run scripts/01_process_cwa_tide_json.py first. "
            f"Missing: {missing}"
        )

    station_info = pd.read_csv(station_path)
    annual_tide = pd.read_csv(annual_path)
    monthly_tide = pd.read_csv(monthly_path, parse_dates=["date"])
    validate_inputs(station_info, annual_tide, monthly_tide)
    return station_info, annual_tide, monthly_tide


def validate_inputs(
    station_info: pd.DataFrame,
    annual_tide: pd.DataFrame,
    monthly_tide: pd.DataFrame,
) -> None:
    if len(station_info) != 2:
        raise ValueError(f"station_info_yunlin_tide.csv should have 2 rows, got {len(station_info)}.")
    if len(annual_tide) != 40:
        raise ValueError(f"annual_tide_yunlin.csv should have 40 rows, got {len(annual_tide)}.")
    if len(monthly_tide) != 480:
        raise ValueError(f"monthly_tide_yunlin.csv should have 480 rows, got {len(monthly_tide)}.")

    for station_name, group in annual_tide.groupby("station_name"):
        if len(group) != 20:
            raise ValueError(f"{station_name}: annual data should have 20 rows.")
        years = group.sort_values("year")["year"].tolist()
        if years != list(range(2006, 2026)):
            raise ValueError(f"{station_name}: expected years 2006-2025, got {years}.")

    for station_name, group in monthly_tide.groupby("station_name"):
        if len(group) != 240:
            raise ValueError(f"{station_name}: monthly data should have 240 rows.")

    for frame_name, frame in {"annual": annual_tide, "monthly": monthly_tide}.items():
        for column in ["mean_tide_level", "highest_high_water_level", "hhw_minus_hat"]:
            if not pd.api.types.is_numeric_dtype(frame[column]):
                raise TypeError(f"{frame_name}.{column} must be numeric.")


def plot_eda(monthly_tide: pd.DataFrame, annual_tide: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 5))
    sns.lineplot(
        data=monthly_tide,
        x="date",
        y="mean_tide_level",
        hue="station_name",
        marker="o",
        linewidth=1.5,
        markersize=3,
    )
    plt.title("Monthly Mean Tide Level, 2006-2025")
    plt.xlabel("Date")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("01_monthly_mean_tide_timeseries.png")

    plt.figure(figsize=(10, 5))
    sns.boxplot(
        data=monthly_tide,
        x="month",
        y="mean_tide_level",
        hue="station_name",
    )
    plt.title("Seasonality of Monthly Mean Tide Level")
    plt.xlabel("Month")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("02_monthly_tide_boxplot.png")

    plt.figure(figsize=(10, 5))
    for station_name, group in annual_tide.groupby("station_name"):
        group = group.sort_values("year")
        x = group["year"].to_numpy(dtype=float)
        y = group["mean_tide_level"].to_numpy(dtype=float)
        slope, intercept, *_ = stats.linregress(x, y)
        plt.scatter(x, y, label=f"{station_name} observed")
        plt.plot(x, intercept + slope * x, label=f"{station_name} trend")
    plt.title("Annual Mean Sea Level Trend")
    plt.xlabel("Year")
    plt.ylabel("Annual mean sea level (m, TWVD2001)")
    plt.legend()
    save_fig("03_annual_mean_sea_level_trend.png")

    plt.figure(figsize=(10, 5))
    sns.lineplot(
        data=annual_tide,
        x="year",
        y="highest_high_water_level",
        hue="station_name",
        marker="o",
    )
    plt.title("Annual Maximum High-Water Level")
    plt.xlabel("Year")
    plt.ylabel("Highest high-water level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("04_annual_max_high_water_timeseries.png")


def mann_kendall_test(years: np.ndarray, values: np.ndarray) -> tuple[float, float, float]:
    n = len(values)
    s = 0.0
    for i in range(n - 1):
        s += np.sign(values[i + 1 :] - values[i]).sum()

    _, counts = np.unique(values, return_counts=True)
    tie_term = sum(count * (count - 1) * (2 * count + 5) for count in counts if count > 1)
    variance = (n * (n - 1) * (2 * n + 5) - tie_term) / 18

    if variance == 0:
        z = 0.0
    elif s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0

    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    slopes = [
        (values[j] - values[i]) / (years[j] - years[i])
        for i in range(n - 1)
        for j in range(i + 1, n)
        if years[j] != years[i]
    ]
    sen_slope = float(np.median(slopes)) if slopes else np.nan
    return float(s), float(p_value), sen_slope


def run_trend_analysis(annual_tide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for station_name, group in annual_tide.groupby("station_name"):
        group = group.sort_values("year")
        years = group["year"].to_numpy(dtype=float)
        values = group["mean_tide_level"].to_numpy(dtype=float)
        regression = stats.linregress(years, values)
        mk_s, mk_p_value, sen_slope = mann_kendall_test(years, values)

        if mk_p_value < 0.05 and sen_slope > 0:
            conclusion = "significant increasing"
        elif mk_p_value < 0.05 and sen_slope < 0:
            conclusion = "significant decreasing"
        else:
            conclusion = "not significant"

        rows.append(
            {
                "station_name": station_name,
                "n_years": len(group),
                "linear_slope_m_per_year": regression.slope,
                "linear_slope_mm_per_year": regression.slope * 1000,
                "linear_p_value": regression.pvalue,
                "r_squared": regression.rvalue**2,
                "mk_statistic_s": mk_s,
                "mk_p_value": mk_p_value,
                "sen_slope_m_per_year": sen_slope,
                "sen_slope_mm_per_year": sen_slope * 1000,
                "conclusion": conclusion,
            }
        )

    trend_results = pd.DataFrame(rows)
    trend_results.to_csv(TABLE_DIR / "trend_results.csv", index=False, encoding="utf-8-sig")
    return trend_results


def fit_distribution(values: np.ndarray, station_name: str, distribution: str) -> FitResult:
    if distribution == "Gumbel":
        params = stats.gumbel_r.fit(values)
        log_likelihood = float(np.sum(stats.gumbel_r.logpdf(values, *params)))
    elif distribution == "GEV":
        params = stats.genextreme.fit(values)
        log_likelihood = float(np.sum(stats.genextreme.logpdf(values, *params)))
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    k = len(params)
    n = len(values)
    aic = 2 * k - 2 * log_likelihood
    bic = k * math.log(n) - 2 * log_likelihood
    return FitResult(
        station_name=station_name,
        distribution=distribution,
        params=tuple(float(param) for param in params),
        log_likelihood=log_likelihood,
        aic=aic,
        bic=bic,
    )


def distribution_pdf(x_values: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.pdf(x_values, *fit.params)
    return stats.genextreme.pdf(x_values, *fit.params)


def distribution_ppf(probabilities: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.ppf(probabilities, *fit.params)
    return stats.genextreme.ppf(probabilities, *fit.params)


def station_slug(station_name: str) -> str:
    return STATION_SLUGS.get(station_name, station_name.lower().replace(" ", "_"))


def run_extreme_value_analysis(
    annual_tide: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parameter_rows = []
    metric_rows = []
    return_rows = []

    for station_name, group in annual_tide.groupby("station_name"):
        values = np.sort(group["highest_high_water_level"].dropna().to_numpy(dtype=float))
        if len(values) < 8:
            warnings.warn(f"{station_name}: too few annual maxima for extreme-value fitting.")
            continue

        fits = [
            fit_distribution(values, station_name, "Gumbel"),
            fit_distribution(values, station_name, "GEV"),
        ]
        slug = station_slug(station_name)

        for fit in fits:
            if fit.distribution == "Gumbel":
                parameter_rows.append(
                    {
                        "station_name": station_name,
                        "distribution": fit.distribution,
                        "location": fit.params[0],
                        "scale": fit.params[1],
                        "shape": np.nan,
                    }
                )
            else:
                parameter_rows.append(
                    {
                        "station_name": station_name,
                        "distribution": fit.distribution,
                        "location": fit.params[1],
                        "scale": fit.params[2],
                        "shape": fit.params[0],
                    }
                )

            metric_rows.append(
                {
                    "station_name": station_name,
                    "distribution": fit.distribution,
                    "log_likelihood": fit.log_likelihood,
                    "aic": fit.aic,
                    "bic": fit.bic,
                    "n": len(values),
                }
            )

            for return_period in RETURN_PERIODS:
                exceedance_probability = 1 / return_period
                return_rows.append(
                    {
                        "station_name": station_name,
                        "distribution": fit.distribution,
                        "return_period_years": return_period,
                        "annual_exceedance_probability": exceedance_probability,
                        "return_level": distribution_ppf(
                            np.array([1 - exceedance_probability]),
                            fit,
                        )[0],
                    }
                )

        plot_histogram_with_fits(station_name, slug, values, fits)
        plot_qq(station_name, slug, values, fits)
        plot_return_level(station_name, slug, fits)

    parameters = pd.DataFrame(parameter_rows)
    metrics = pd.DataFrame(metric_rows)
    return_levels = pd.DataFrame(return_rows)

    parameters.to_csv(TABLE_DIR / "extreme_value_parameters.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(TABLE_DIR / "model_fit_metrics.csv", index=False, encoding="utf-8-sig")
    return_levels.to_csv(TABLE_DIR / "return_levels.csv", index=False, encoding="utf-8-sig")
    return parameters, metrics, return_levels


def plot_histogram_with_fits(
    station_name: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    padding = values.std(ddof=1) if len(values) > 1 else 0.1
    x_values = np.linspace(values.min() - padding, values.max() + padding, 300)

    plt.figure(figsize=(8, 5))
    sns.histplot(values, stat="density", bins="auto", color="lightgray", edgecolor="black")
    for fit in fits:
        plt.plot(x_values, distribution_pdf(x_values, fit), label=fit.distribution)
    plt.title(f"{station_name}: Annual Maximum High-Water Distribution")
    plt.xlabel("Highest high-water level (m, TWVD2001)")
    plt.ylabel("Density")
    plt.legend()
    figure_number = "05" if slug == "mailiao" else "06"
    save_fig(f"{figure_number}_histogram_fitted_pdf_{slug}.png")


def plot_qq(
    station_name: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    probabilities = (np.arange(1, len(values) + 1) - 0.5) / len(values)
    theoretical_values = [distribution_ppf(probabilities, fit) for fit in fits]
    min_axis = min(values.min(), *(series.min() for series in theoretical_values))
    max_axis = max(values.max(), *(series.max() for series in theoretical_values))

    plt.figure(figsize=(6, 6))
    for fit, theoretical in zip(fits, theoretical_values, strict=True):
        plt.scatter(theoretical, values, label=fit.distribution)
    plt.plot([min_axis, max_axis], [min_axis, max_axis], color="black", linestyle="--")
    plt.title(f"{station_name}: Q-Q Plot")
    plt.xlabel("Theoretical quantiles")
    plt.ylabel("Observed annual maxima")
    plt.legend()
    figure_number = "07" if slug == "mailiao" else "08"
    save_fig(f"{figure_number}_qq_plot_{slug}.png")


def plot_return_level(station_name: str, slug: str, fits: list[FitResult]) -> None:
    periods = np.arange(2, 101)
    probabilities = 1 - 1 / periods

    plt.figure(figsize=(8, 5))
    for fit in fits:
        plt.plot(periods, distribution_ppf(probabilities, fit), label=fit.distribution)
    plt.title(f"{station_name}: Return Level Plot")
    plt.xlabel("Return period (years)")
    plt.ylabel("Return level (m, TWVD2001)")
    plt.legend()
    figure_number = "09" if slug == "mailiao" else "10"
    filename_slug = "bozilio" if slug == "boziliao" else slug
    save_fig(f"{figure_number}_return_level_plot_{filename_slug}.png")


def run_extreme_year_sensitivity(annual_tide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for station_name, group in annual_tide.groupby("station_name"):
        group = group.sort_values("year")
        values = group["highest_high_water_level"].to_numpy(dtype=float)
        max_index = int(np.argmax(values))
        removed_year = int(group.iloc[max_index]["year"])

        scenarios = {
            "all_years": values,
            "remove_largest_year": np.delete(values, max_index),
        }
        for scenario, scenario_values in scenarios.items():
            for distribution in ["Gumbel", "GEV"]:
                fit = fit_distribution(scenario_values, station_name, distribution)
                for return_period in [50, 100]:
                    rows.append(
                        {
                            "station_name": station_name,
                            "scenario": scenario,
                            "removed_year": np.nan if scenario == "all_years" else removed_year,
                            "distribution": distribution,
                            "return_period_years": return_period,
                            "return_level": distribution_ppf(
                                np.array([1 - 1 / return_period]),
                                fit,
                            )[0],
                        }
                    )

    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(
        TABLE_DIR / "sensitivity_extreme_year.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return sensitivity


def run_data_length_sensitivity(annual_tide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    periods = {
        "all_years": None,
        "last_15_years": 15,
        "last_10_years": 10,
    }

    for station_name, group in annual_tide.groupby("station_name"):
        group = group.sort_values("year")
        for period_name, n_years in periods.items():
            period_group = group if n_years is None else group.tail(n_years)
            values = period_group["highest_high_water_level"].to_numpy(dtype=float)
            for distribution in ["Gumbel", "GEV"]:
                fit = fit_distribution(values, station_name, distribution)
                rows.append(
                    {
                        "station_name": station_name,
                        "period": period_name,
                        "distribution": distribution,
                        "n_years": len(values),
                        "return_level_50yr": distribution_ppf(np.array([1 - 1 / 50]), fit)[0],
                        "return_level_100yr": distribution_ppf(np.array([1 - 1 / 100]), fit)[0],
                    }
                )

    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(
        TABLE_DIR / "sensitivity_data_length.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return sensitivity


def write_summary(
    station_info: pd.DataFrame,
    trend_results: pd.DataFrame,
    model_metrics: pd.DataFrame,
    return_levels: pd.DataFrame,
    extreme_sensitivity: pd.DataFrame,
    length_sensitivity: pd.DataFrame,
) -> None:
    lines = [
        "# Analysis Summary",
        "",
        "Generated by `scripts/02_analyze_yunlin_tides.py`.",
        "",
        "## Data",
        "",
        station_info.to_markdown(index=False),
        "",
        "The analysis uses relative water levels referenced to TWVD2001.",
        "",
        "## Trend Results",
        "",
        trend_results.to_markdown(index=False),
        "",
        "## Extreme-Value Model Fit",
        "",
        model_metrics.to_markdown(index=False),
        "",
        "## Return Levels",
        "",
        return_levels.to_markdown(index=False),
        "",
        "## Extreme-Year Sensitivity",
        "",
        extreme_sensitivity.to_markdown(index=False),
        "",
        "## Data-Length Sensitivity",
        "",
        length_sensitivity.to_markdown(index=False),
        "",
        "## Interpretation Notes",
        "",
        "- Trends should be interpreted as relative sea-level change, not direct global sea-level rise.",
        "- The annual maximum high-water level includes astronomical and meteorological effects.",
        "- With only 20 years of data, 50- and 100-year return levels have high uncertainty.",
        "- GEV is flexible, but its shape parameter may be unstable for short records.",
        "- The two tide stations support comparison along the Yunlin coast but do not fully represent the entire coastline.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def analyze() -> None:
    ensure_directories()
    configure_plots()
    station_info, annual_tide, monthly_tide = load_processed_data()

    plot_eda(monthly_tide, annual_tide)
    trend_results = run_trend_analysis(annual_tide)
    _, model_metrics, return_levels = run_extreme_value_analysis(annual_tide)
    extreme_sensitivity = run_extreme_year_sensitivity(annual_tide)
    length_sensitivity = run_data_length_sensitivity(annual_tide)
    write_summary(
        station_info,
        trend_results,
        model_metrics,
        return_levels,
        extreme_sensitivity,
        length_sensitivity,
    )

    print("Analysis complete.")
    print(f"Figures written to: {FIG_DIR}")
    print(f"Tables written to: {TABLE_DIR}")
    print(f"Summary written to: {SUMMARY_PATH}")


if __name__ == "__main__":
    analyze()
