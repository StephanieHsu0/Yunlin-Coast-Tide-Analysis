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
ALTERNATIVE_RETURN_PERIODS = [2, 5, 10, 20, 50, 100]
ALL_DISTRIBUTIONS = ["Gumbel", "GEV", "Lognormal", "Pearson Type III"]
STATION_SLUGS = {
    "麥寮潮位站": "mailiao",
    "萡子寮潮位站": "boziliao",
}
STATION_LABELS = {
    "麥寮潮位站": "Mailiao",
    "萡子寮潮位站": "Boziliao",
}
HISTOGRAM_BINS = {
    "Mailiao": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Boziliao": [1.5, 1.75, 2.0, 2.25, 2.5, 2.75],
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


def format_year_axis(start_year: int = 2006, end_year: int = 2025, step: int = 2) -> None:
    """Show only integer years on annual-data figures."""
    plt.xticks(np.arange(start_year, end_year + 1, step))


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

    for data in [annual_tide, monthly_tide]:
        data["station_label"] = data["station_name"].map(STATION_LABELS).fillna(data["station_name"])

    monthly_tide = apply_monthly_quality_flags(monthly_tide)
    return station_info, annual_tide, monthly_tide


def apply_monthly_quality_flags(monthly_tide: pd.DataFrame) -> pd.DataFrame:
    monthly_tide = monthly_tide.copy()
    incomplete_mask = (
        (monthly_tide["station_name"] == "麥寮潮位站")
        & (monthly_tide["year"] == 2015)
        & (monthly_tide["month"].isin([1, 2, 3, 4, 5, 6, 7]))
    )
    monthly_tide["data_quality_flag"] = "normal"
    monthly_tide.loc[incomplete_mask, "data_quality_flag"] = "partial_or_incomplete_record"
    monthly_tide["is_valid_monthly_mean_for_eda"] = (
        monthly_tide["data_quality_flag"] != "partial_or_incomplete_record"
    )
    return monthly_tide


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
    monthly_plot_df = monthly_tide.copy()
    incomplete_mask = ~monthly_plot_df["is_valid_monthly_mean_for_eda"]
    monthly_plot_df.loc[incomplete_mask, "mean_tide_level"] = np.nan
    monthly_analysis_df = monthly_tide[monthly_tide["is_valid_monthly_mean_for_eda"]].copy()

    plt.figure(figsize=(12, 5))
    sns.lineplot(
        data=monthly_tide,
        x="date",
        y="mean_tide_level",
        hue="station_label",
        marker="o",
        linewidth=1.5,
        markersize=3,
    )
    plt.title("Monthly Mean Tide Level, 2006-2025 (Raw)")
    plt.xlabel("Date")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("01_monthly_mean_tide_timeseries_raw.png")

    plt.figure(figsize=(10, 5))
    sns.boxplot(
        data=monthly_tide,
        x="month",
        y="mean_tide_level",
        hue="station_label",
    )
    plt.title("Seasonality of Monthly Mean Tide Level (Raw)")
    plt.xlabel("Month")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("02_monthly_tide_boxplot_raw.png")

    fig, ax = plt.subplots(figsize=(12, 5))
    for station_label, group in monthly_plot_df.groupby("station_label"):
        group = group.sort_values("date")
        ax.plot(
            group["date"],
            group["mean_tide_level"],
            marker="o",
            linewidth=1.5,
            markersize=3,
            label=station_label,
        )
    ax.axvspan(
        pd.Timestamp("2015-01-01"),
        pd.Timestamp("2015-07-31"),
        color="gray",
        alpha=0.15,
        label="Mailiao Jan-Jul 2015 incomplete",
    )
    plt.title("Monthly Mean Tide Level, 2006-2025 (QC-filtered)")
    plt.xlabel("Date")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    plt.text(
        0.01,
        0.95,
        "Mailiao Jan-Jul 2015 incomplete records were excluded; missing period is shown as a gap.",
        transform=plt.gca().transAxes,
        fontsize=9,
        verticalalignment="top",
    )
    save_fig("15_monthly_mean_tide_timeseries_qc.png")

    plt.figure(figsize=(10, 5))
    sns.boxplot(
        data=monthly_analysis_df,
        x="month",
        y="mean_tide_level",
        hue="station_label",
    )
    plt.title("Seasonality of Monthly Mean Tide Level (QC-filtered)")
    plt.xlabel("Month")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.legend(title="Station")
    save_fig("16_monthly_tide_boxplot_qc.png")

    plt.figure(figsize=(10, 5))
    for station_name, group in annual_tide.groupby("station_name"):
        group = group.sort_values("year")
        station_label = group["station_label"].iloc[0]
        x = group["year"].to_numpy(dtype=float)
        y = group["mean_tide_level"].to_numpy(dtype=float)
        slope, intercept, *_ = stats.linregress(x, y)
        plt.scatter(x, y, label=f"{station_label} observed")
        plt.plot(x, intercept + slope * x, label=f"{station_label} trend")
    plt.title("Annual Mean Sea Level Trend")
    plt.xlabel("Year")
    plt.ylabel("Annual mean sea level (m, TWVD2001)")
    plt.legend()
    format_year_axis()
    save_fig("03_annual_mean_sea_level_trend.png")

    plt.figure(figsize=(10, 5))
    sns.lineplot(
        data=annual_tide,
        x="year",
        y="highest_high_water_level",
        hue="station_label",
        marker="o",
    )
    mailiao_2018 = annual_tide[
        (annual_tide["station_label"] == "Mailiao") & (annual_tide["year"] == 2018)
    ]
    if not mailiao_2018.empty:
        row = mailiao_2018.iloc[0]
        plt.annotate(
            "Mailiao 2018 extreme",
            xy=(row["year"], row["highest_high_water_level"]),
            xytext=(row["year"] + 1.2, row["highest_high_water_level"] - 0.28),
            arrowprops={"arrowstyle": "->", "color": "black"},
            fontsize=10,
        )
    plt.title("Annual Maximum High-Water Level")
    plt.xlabel("Year")
    plt.ylabel("Highest high-water level (m, TWVD2001)")
    plt.legend(title="Station")
    format_year_axis()
    save_fig("04_annual_max_high_water_timeseries.png")

    plt.figure(figsize=(10, 5))
    sns.lineplot(
        data=annual_tide,
        x="year",
        y="hhw_minus_hat",
        hue="station_label",
        marker="o",
    )
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    mailiao_2018_hhw = annual_tide[
        (annual_tide["station_label"] == "Mailiao") & (annual_tide["year"] == 2018)
    ]
    if not mailiao_2018_hhw.empty:
        row = mailiao_2018_hhw.iloc[0]
        plt.annotate(
            "Mailiao 2018",
            xy=(row["year"], row["hhw_minus_hat"]),
            xytext=(row["year"] + 1.0, row["hhw_minus_hat"] - 0.25),
            arrowprops={"arrowstyle": "->", "color": "black"},
            fontsize=10,
        )
    plt.title("Difference between Highest High Water and Highest Astronomical Tide")
    plt.xlabel("Year")
    plt.ylabel("HHW - HAT (m)")
    plt.legend(title="Station")
    format_year_axis()
    save_fig("11_hhw_minus_hat_timeseries.png")


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


def run_trend_based_sensitivity(trend_results: pd.DataFrame) -> pd.DataFrame:
    """Project relative background water-level change from Sen's slope.

    This is a trend-based sensitivity scenario, not a precise prediction. It
    does not replace extreme-value distribution uncertainty; it only illustrates
    how continued background relative sea-level rise could raise future design
    water levels.
    """
    rows = []
    for _, row in trend_results.iterrows():
        station_name = row["station_name"]
        station_label = STATION_LABELS.get(station_name, station_name)
        sen_slope_m_per_year = row["sen_slope_m_per_year"]
        sen_slope_mm_per_year = row["sen_slope_mm_per_year"]
        for years_ahead in [10, 25, 50]:
            projected_increase_m = sen_slope_m_per_year * years_ahead
            rows.append(
                {
                    "station_name": station_name,
                    "station_label": station_label,
                    "sen_slope_mm_per_year": sen_slope_mm_per_year,
                    "years_ahead": years_ahead,
                    "projected_increase_m": projected_increase_m,
                    "projected_increase_cm": projected_increase_m * 100,
                    "note": "Scenario only; assumes observed linear Sen’s slope continues.",
                }
            )

    trend_sensitivity = pd.DataFrame(rows)
    trend_sensitivity.to_csv(
        TABLE_DIR / "trend_based_sensitivity.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.figure(figsize=(8, 5))
    sns.barplot(
        data=trend_sensitivity,
        x="years_ahead",
        y="projected_increase_m",
        hue="station_label",
    )
    plt.title("Trend-Based Relative Sea-Level Sensitivity")
    plt.xlabel("Years ahead")
    plt.ylabel("Projected increase (m)")
    plt.legend(title="Station")
    save_fig("trend_based_sensitivity.png")

    return trend_sensitivity


def iqr_outliers(data: pd.DataFrame, value_column: str, group_column: str = "station_name") -> pd.DataFrame:
    rows = []
    for station_name, group in data.groupby(group_column):
        values = group[value_column].dropna()
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outlier_rows = group[
            (group[value_column] < lower_bound) | (group[value_column] > upper_bound)
        ].copy()
        if outlier_rows.empty:
            continue

        outlier_rows["outlier_variable"] = value_column
        outlier_rows["outlier_type"] = np.where(
            outlier_rows[value_column] > upper_bound,
            "high",
            "low",
        )
        outlier_rows["q1"] = q1
        outlier_rows["q3"] = q3
        outlier_rows["iqr"] = iqr
        outlier_rows["lower_bound"] = lower_bound
        outlier_rows["upper_bound"] = upper_bound
        rows.append(outlier_rows)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def write_outlier_tables(monthly_tide: pd.DataFrame, annual_tide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_columns = [
        "station_name",
        "station_label",
        "year",
        "month",
        "date",
        "mean_tide_level",
        "lower_bound",
        "upper_bound",
        "outlier_type",
    ]
    annual_columns = [
        "station_name",
        "station_label",
        "year",
        "highest_high_water_level",
        "lower_bound",
        "upper_bound",
        "outlier_type",
    ]

    monthly_outliers = iqr_outliers(monthly_tide, "mean_tide_level")
    annual_outliers = iqr_outliers(annual_tide, "highest_high_water_level")

    monthly_outliers = monthly_outliers.reindex(columns=monthly_columns)
    annual_outliers = annual_outliers.reindex(columns=annual_columns)
    monthly_outliers.to_csv(TABLE_DIR / "monthly_outliers.csv", index=False, encoding="utf-8-sig")
    annual_outliers.to_csv(TABLE_DIR / "annual_outliers.csv", index=False, encoding="utf-8-sig")
    return monthly_outliers, annual_outliers


def plot_monthly_outliers(monthly_tide: pd.DataFrame, monthly_outliers: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 5))
    sns.lineplot(
        data=monthly_tide,
        x="date",
        y="mean_tide_level",
        hue="station_label",
        linewidth=1.5,
    )
    if not monthly_outliers.empty:
        sns.scatterplot(
            data=monthly_outliers,
            x="date",
            y="mean_tide_level",
            hue="station_label",
            style="outlier_type",
            s=100,
            edgecolor="black",
            legend=False,
        )
    plt.title("Monthly Mean Tide Level with IQR Outliers Marked")
    plt.xlabel("Date")
    plt.ylabel("Mean tide level (m, TWVD2001)")
    plt.text(
        0.01,
        0.95,
        "Markers indicate IQR-based outliers",
        transform=plt.gca().transAxes,
        fontsize=10,
        verticalalignment="top",
    )
    plt.legend(title="Station")
    save_fig("12_monthly_mean_tide_outliers_marked.png")


def write_incomplete_monthly_records(monthly_tide: pd.DataFrame) -> pd.DataFrame:
    incomplete_records = monthly_tide[
        monthly_tide["data_quality_flag"] == "partial_or_incomplete_record"
    ].copy()
    columns = [
        "station_name",
        "station_label",
        "year",
        "month",
        "date",
        "mean_tide_level",
        "highest_high_water_level",
        "mean_high_water_level",
        "mean_low_water_level",
        "mean_tidal_range",
        "data_quality_flag",
    ]
    incomplete_records = incomplete_records.reindex(columns=columns)
    incomplete_records.to_csv(
        TABLE_DIR / "incomplete_monthly_records.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return incomplete_records


def write_valid_month_counts(monthly_tide: pd.DataFrame) -> pd.DataFrame:
    monthly_counts = monthly_tide.copy()
    monthly_counts["valid_for_monthly_eda"] = (
        monthly_counts["is_valid_monthly_mean_for_eda"] & monthly_counts["mean_tide_level"].notna()
    )
    valid_month_counts = (
        monthly_counts.groupby(["station_name", "station_label", "year"])
        .agg(
            valid_month_count=("valid_for_monthly_eda", "sum"),
            incomplete_month_count=(
                "data_quality_flag",
                lambda values: (values == "partial_or_incomplete_record").sum(),
            ),
            missing_mean_tide_count=("mean_tide_level", lambda values: values.isna().sum()),
        )
        .reset_index()
    )
    valid_month_counts["meets_10_month_threshold"] = valid_month_counts["valid_month_count"] >= 10
    valid_month_counts.to_csv(
        TABLE_DIR / "valid_month_counts.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return valid_month_counts


def write_top_extreme_years(annual_tide: pd.DataFrame) -> pd.DataFrame:
    top_extremes = (
        annual_tide.sort_values(["station_name", "highest_high_water_level"], ascending=[True, False])
        .groupby("station_name")
        .head(5)
        .copy()
    )
    top_extremes["rank"] = top_extremes.groupby("station_name")["highest_high_water_level"].rank(
        method="first",
        ascending=False,
    ).astype(int)
    top_extremes = top_extremes[
        [
            "station_name",
            "station_label",
            "rank",
            "year",
            "highest_high_water_level",
            "highest_astronomical_tide",
            "hhw_minus_hat",
            "mean_tide_level",
        ]
    ].sort_values(["station_name", "rank"])
    top_extremes.to_csv(TABLE_DIR / "top_extreme_years.csv", index=False, encoding="utf-8-sig")
    return top_extremes


def write_mailiao_2018_monthly_check(monthly_tide: pd.DataFrame) -> pd.DataFrame:
    mailiao_2018 = monthly_tide[
        (monthly_tide["station_name"] == "麥寮潮位站") & (monthly_tide["year"] == 2018)
    ].copy()
    mailiao_2018 = mailiao_2018.sort_values("highest_high_water_level", ascending=False)
    mailiao_2018 = mailiao_2018[
        [
            "station_name",
            "station_label",
            "year",
            "month",
            "date",
            "highest_high_water_level",
            "highest_astronomical_tide",
            "hhw_minus_hat",
            "mean_tide_level",
        ]
    ]
    mailiao_2018.to_csv(
        TABLE_DIR / "mailiao_2018_monthly_check.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return mailiao_2018


def write_summary_statistics(annual_tide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    variables = ["mean_tide_level", "highest_high_water_level"]
    for station_name, group in annual_tide.groupby("station_name"):
        station_label = group["station_label"].iloc[0]
        for variable in variables:
            values = group[variable].dropna()
            rows.append(
                {
                    "station_name": station_name,
                    "station_label": station_label,
                    "variable": variable,
                    "mean": values.mean(),
                    "std": values.std(ddof=1),
                    "min": values.min(),
                    "max": values.max(),
                    "median": values.median(),
                    "skewness": values.skew(),
                }
            )

    summary_statistics = pd.DataFrame(rows)
    summary_statistics.to_csv(TABLE_DIR / "summary_statistics.csv", index=False, encoding="utf-8-sig")
    return summary_statistics


def fit_distribution(values: np.ndarray, station_name: str, distribution: str) -> FitResult:
    if distribution == "Gumbel":
        params = stats.gumbel_r.fit(values)
        log_likelihood = float(np.sum(stats.gumbel_r.logpdf(values, *params)))
    elif distribution == "GEV":
        params = stats.genextreme.fit(values)
        log_likelihood = float(np.sum(stats.genextreme.logpdf(values, *params)))
    elif distribution == "Lognormal":
        params = stats.lognorm.fit(values, floc=0)
        log_likelihood = float(np.sum(stats.lognorm.logpdf(values, *params)))
    elif distribution == "Pearson Type III":
        params = stats.pearson3.fit(values)
        log_likelihood = float(np.sum(stats.pearson3.logpdf(values, *params)))
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
    if fit.distribution == "GEV":
        return stats.genextreme.pdf(x_values, *fit.params)
    if fit.distribution == "Lognormal":
        return stats.lognorm.pdf(x_values, *fit.params)
    return stats.pearson3.pdf(x_values, *fit.params)


def distribution_ppf(probabilities: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.ppf(probabilities, *fit.params)
    if fit.distribution == "GEV":
        return stats.genextreme.ppf(probabilities, *fit.params)
    if fit.distribution == "Lognormal":
        return stats.lognorm.ppf(probabilities, *fit.params)
    return stats.pearson3.ppf(probabilities, *fit.params)


def distribution_cdf(x_values: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.cdf(x_values, *fit.params)
    if fit.distribution == "GEV":
        return stats.genextreme.cdf(x_values, *fit.params)
    if fit.distribution == "Lognormal":
        return stats.lognorm.cdf(x_values, *fit.params)
    return stats.pearson3.cdf(x_values, *fit.params)


def empirical_ad_statistic(values: np.ndarray, fit: FitResult) -> float:
    """Empirical Anderson-Darling statistic using the fitted CDF.

    AD is useful for extremes because it gives more weight to distribution tails
    than central-fit statistics. Values are clipped to avoid log(0).
    """
    sorted_values = np.sort(values)
    n = len(sorted_values)
    cdf_values = np.clip(distribution_cdf(sorted_values, fit), 1e-10, 1 - 1e-10)
    i = np.arange(1, n + 1)
    ad_value = -n - np.mean(
        (2 * i - 1)
        * (np.log(cdf_values) + np.log(1 - cdf_values[::-1]))
    )
    return float(ad_value)


def goodness_of_fit_metrics(values: np.ndarray, fit: FitResult) -> dict[str, float]:
    """Compute numerical fit diagnostics for a fitted model.

    Lower AIC/BIC values indicate better relative model performance. Smaller
    KS/AD/CVM statistics indicate closer agreement between observed data and
    the fitted distribution. With about 20 annual maxima, these diagnostics are
    supporting evidence rather than the sole model-selection criterion.
    """
    cdf_function = lambda sample: distribution_cdf(np.asarray(sample), fit)
    ks_result = stats.kstest(values, cdf_function)
    cvm_result = stats.cramervonmises(values, cdf_function)
    ad_statistic = empirical_ad_statistic(values, fit)

    return {
        "KS_statistic": float(ks_result.statistic),
        "KS_pvalue": float(ks_result.pvalue),
        "AD_statistic": ad_statistic,
        "CVM_statistic": float(cvm_result.statistic),
    }


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

        station_label = group["station_label"].iloc[0]
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

        plot_histogram_with_fits(station_label, slug, values, fits)
        plot_qq(station_label, slug, values, fits)
        plot_return_level(station_label, slug, fits)
        plot_return_level_logx(station_label, slug, fits)

    parameters = pd.DataFrame(parameter_rows)
    metrics = pd.DataFrame(metric_rows)
    return_levels = pd.DataFrame(return_rows)

    parameters.to_csv(TABLE_DIR / "extreme_value_parameters.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(TABLE_DIR / "model_fit_metrics.csv", index=False, encoding="utf-8-sig")
    return_levels.to_csv(TABLE_DIR / "return_levels.csv", index=False, encoding="utf-8-sig")
    return parameters, metrics, return_levels


def run_all_distribution_analysis(annual_tide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit additional frequency-analysis alternatives without replacing the baseline Gumbel/GEV workflow.

    Gumbel is kept as the stable baseline model. GEV is more flexible but can be
    sensitive under short records because of its shape parameter. Lognormal and
    Pearson Type III are empirical/hydrologic frequency-analysis alternatives.
    Generalized Pareto is not fit here because it requires threshold-exceedance
    data rather than annual block maxima.
    """
    comparison_rows = []
    return_rows = []
    goodness_rows = []

    for station_name, group in annual_tide.groupby("station_name"):
        values = np.sort(group["highest_high_water_level"].dropna().to_numpy(dtype=float))
        if len(values) < 8:
            warnings.warn(f"{station_name}: too few annual maxima for all-distribution fitting.")
            continue

        station_label = group["station_label"].iloc[0]
        slug = station_slug(station_name)
        fits: list[FitResult] = []

        for distribution in ALL_DISTRIBUTIONS:
            try:
                fit = fit_distribution(values, station_name, distribution)
            except Exception as exc:
                warnings.warn(f"{station_name}: {distribution} fitting failed: {exc}")
                comparison_rows.append(
                    {
                        "station_name": station_name,
                        "station_label": station_label,
                        "distribution": distribution,
                        "n": len(values),
                        "log_likelihood": np.nan,
                        "aic": np.nan,
                        "bic": np.nan,
                        "param_1": np.nan,
                        "param_2": np.nan,
                        "param_3": np.nan,
                        "status": f"failed: {exc}",
                    }
                )
                continue

            fits.append(fit)
            params = list(fit.params) + [np.nan] * (3 - len(fit.params))
            try:
                gof = goodness_of_fit_metrics(values, fit)
            except Exception as exc:
                warnings.warn(f"{station_name}: {fit.distribution} goodness-of-fit failed: {exc}")
                gof = {
                    "KS_statistic": np.nan,
                    "KS_pvalue": np.nan,
                    "AD_statistic": np.nan,
                    "CVM_statistic": np.nan,
                }

            comparison_rows.append(
                {
                    "station_name": station_name,
                    "station_label": station_label,
                    "distribution": fit.distribution,
                    "n": len(values),
                    "log_likelihood": fit.log_likelihood,
                    "aic": fit.aic,
                    "bic": fit.bic,
                    "param_1": params[0],
                    "param_2": params[1],
                    "param_3": params[2],
                    "status": "success",
                }
            )
            goodness_rows.append(
                {
                    "station": station_label,
                    "model": fit.distribution,
                    "n": len(values),
                    "number_of_parameters": len(fit.params),
                    "log_likelihood": fit.log_likelihood,
                    "AIC": fit.aic,
                    "BIC": fit.bic,
                    "KS_statistic": gof["KS_statistic"],
                    "KS_pvalue": gof["KS_pvalue"],
                    "AD_statistic": gof["AD_statistic"],
                    "CVM_statistic": gof["CVM_statistic"],
                }
            )

            for return_period in ALTERNATIVE_RETURN_PERIODS:
                exceedance_probability = 1 / return_period
                try:
                    return_level = distribution_ppf(np.array([1 - exceedance_probability]), fit)[0]
                except Exception as exc:
                    warnings.warn(
                        f"{station_name}: {fit.distribution} return level failed "
                        f"for T={return_period}: {exc}"
                    )
                    return_level = np.nan
                return_rows.append(
                    {
                        "station_name": station_name,
                        "station_label": station_label,
                        "distribution": fit.distribution,
                        "return_period_years": return_period,
                        "annual_exceedance_probability": exceedance_probability,
                        "return_level": return_level,
                    }
                )

        if fits:
            plot_histogram_all_distributions(station_label, slug, values, fits)
            plot_qq_all_distributions(station_label, slug, values, fits)
            plot_return_level_all_distributions(station_label, slug, fits)

    comparison = pd.DataFrame(comparison_rows)
    return_levels = pd.DataFrame(return_rows)
    goodness_of_fit = pd.DataFrame(goodness_rows)
    comparison.to_csv(
        TABLE_DIR / "distribution_fit_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return_levels.to_csv(
        TABLE_DIR / "return_levels_all_distributions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    goodness_of_fit.to_csv(
        TABLE_DIR / "goodness_of_fit_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return comparison, return_levels


def plot_histogram_with_fits(
    station_label: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    padding = values.std(ddof=1) if len(values) > 1 else 0.1
    x_values = np.linspace(values.min() - padding, values.max() + padding, 300)
    bins = HISTOGRAM_BINS[station_label]

    plt.figure(figsize=(8, 5))
    sns.histplot(values, stat="density", bins=bins, color="lightgray", edgecolor="black")
    for fit in fits:
        plt.plot(x_values, distribution_pdf(x_values, fit), label=fit.distribution)
    plt.title(f"{station_label}: Annual Maximum High-Water Distribution")
    plt.xlabel("Highest high-water level (m, TWVD2001)")
    plt.ylabel("Density")
    if station_label == "Boziliao":
        plt.xticks(bins, [f"{edge:.2f}" for edge in bins])
        for edge in bins:
            plt.axvline(edge, color="gray", linestyle="--", linewidth=0.6, alpha=0.35)
    plt.legend()
    figure_number = "05" if slug == "mailiao" else "06"
    save_fig(f"{figure_number}_histogram_fitted_pdf_{slug}.png")


def plot_histogram_all_distributions(
    station_label: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    padding = values.std(ddof=1) if len(values) > 1 else 0.1
    x_values = np.linspace(values.min() - padding, values.max() + padding, 300)
    bins = HISTOGRAM_BINS[station_label]

    plt.figure(figsize=(8, 5))
    sns.histplot(values, stat="density", bins=bins, color="lightgray", edgecolor="black")
    for fit in fits:
        pdf_values = distribution_pdf(x_values, fit)
        if np.isfinite(pdf_values).any():
            plt.plot(x_values, pdf_values, label=fit.distribution)
    plt.title(f"{station_label}: Annual Maximum Distribution (all distributions)")
    plt.xlabel("Highest high-water level (m, TWVD2001)")
    plt.ylabel("Density")
    if station_label == "Boziliao":
        plt.xticks(bins, [f"{edge:.2f}" for edge in bins])
        for edge in bins:
            plt.axvline(edge, color="gray", linestyle="--", linewidth=0.6, alpha=0.35)
    plt.legend()
    save_fig(f"alternative_distributions_histogram_{slug}.png")


def plot_qq(
    station_label: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    probabilities = np.arange(1, len(values) + 1) / (len(values) + 1)
    theoretical_values = [distribution_ppf(probabilities, fit) for fit in fits]
    min_axis = min(values.min(), *(series.min() for series in theoretical_values))
    max_axis = max(values.max(), *(series.max() for series in theoretical_values))

    plt.figure(figsize=(6, 6))
    for fit, theoretical in zip(fits, theoretical_values, strict=True):
        plt.scatter(theoretical, values, label=fit.distribution)
    plt.plot([min_axis, max_axis], [min_axis, max_axis], color="black", linestyle="--")
    plt.title(f"{station_label}: Q-Q Plot")
    plt.xlabel("Theoretical quantiles")
    plt.ylabel("Observed annual maxima")
    plt.legend()
    figure_number = "07" if slug == "mailiao" else "08"
    save_fig(f"{figure_number}_qq_plot_{slug}.png")


def plot_qq_all_distributions(
    station_label: str,
    slug: str,
    values: np.ndarray,
    fits: list[FitResult],
) -> None:
    probabilities = np.arange(1, len(values) + 1) / (len(values) + 1)
    theoretical_values = []
    for fit in fits:
        try:
            theoretical_values.append((fit, distribution_ppf(probabilities, fit)))
        except Exception as exc:
            warnings.warn(f"{station_label}: {fit.distribution} Q-Q plotting failed: {exc}")

    if not theoretical_values:
        return

    min_axis = min(values.min(), *(series.min() for _, series in theoretical_values))
    max_axis = max(values.max(), *(series.max() for _, series in theoretical_values))

    plt.figure(figsize=(7, 7))
    for fit, theoretical in theoretical_values:
        plt.scatter(theoretical, values, label=fit.distribution)
    plt.plot([min_axis, max_axis], [min_axis, max_axis], color="black", linestyle="--")
    plt.title(f"{station_label}: Q-Q Plot (all distributions)")
    plt.xlabel("Theoretical quantiles")
    plt.ylabel("Observed annual maxima")
    plt.legend()
    save_fig(f"all_distributions_qq_plot_{slug}.png")


def plot_return_level(station_label: str, slug: str, fits: list[FitResult]) -> None:
    periods = np.arange(2, 101)
    probabilities = 1 - 1 / periods

    plt.figure(figsize=(8, 5))
    for fit in fits:
        plt.plot(periods, distribution_ppf(probabilities, fit), label=fit.distribution)
    plt.title(f"{station_label}: Return Level Plot")
    plt.xlabel("Return period (years)")
    plt.ylabel("Return level (m, TWVD2001)")
    plt.legend()
    figure_number = "09" if slug == "mailiao" else "10"
    save_fig(f"{figure_number}_return_level_plot_{slug}.png")


def plot_return_level_all_distributions(
    station_label: str,
    slug: str,
    fits: list[FitResult],
) -> None:
    periods = np.arange(2, 101)
    probabilities = 1 - 1 / periods

    plt.figure(figsize=(8, 5))
    for fit in fits:
        try:
            levels = distribution_ppf(probabilities, fit)
        except Exception as exc:
            warnings.warn(f"{station_label}: {fit.distribution} return-level plotting failed: {exc}")
            continue
        plt.plot(periods, levels, label=fit.distribution)
    plt.xscale("log")
    plt.xticks([2, 5, 10, 20, 50, 100], [2, 5, 10, 20, 50, 100])
    plt.title(f"{station_label}: Return Level Plot (all distributions)")
    plt.xlabel("Return period (years)")
    plt.ylabel("Return level (m, TWVD2001)")
    plt.legend()
    save_fig(f"all_distributions_return_level_plot_{slug}.png")


def plot_return_level_logx(station_label: str, slug: str, fits: list[FitResult]) -> None:
    periods = np.arange(2, 101)
    probabilities = 1 - 1 / periods

    plt.figure(figsize=(8, 5))
    for fit in fits:
        plt.plot(periods, distribution_ppf(probabilities, fit), label=fit.distribution)
    plt.xscale("log")
    plt.xticks([2, 5, 10, 20, 50, 100], [2, 5, 10, 20, 50, 100])
    plt.title(f"{station_label}: Return Level Plot (log x-axis)")
    plt.xlabel("Return period (years)")
    plt.ylabel("Return level (m, TWVD2001)")
    plt.legend()
    figure_number = "13" if slug == "mailiao" else "14"
    save_fig(f"{figure_number}_return_level_plot_{slug}_logx.png")


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
                        "reliability_note": "low sample size" if len(values) < 15 else "acceptable",
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
    summary_statistics: pd.DataFrame,
    monthly_outliers: pd.DataFrame,
    incomplete_monthly_records: pd.DataFrame,
    valid_month_counts: pd.DataFrame,
    annual_outliers: pd.DataFrame,
    top_extremes: pd.DataFrame,
    mailiao_2018_monthly_check: pd.DataFrame,
    trend_results: pd.DataFrame,
    trend_sensitivity: pd.DataFrame,
    model_metrics: pd.DataFrame,
    return_levels: pd.DataFrame,
    extreme_sensitivity: pd.DataFrame,
    length_sensitivity: pd.DataFrame,
) -> None:
    mailiao_2018_peak = mailiao_2018_monthly_check.iloc[0]
    mailiao_2018_month = int(mailiao_2018_peak["month"])
    not_august_note = (
        "- The peak month is not August, so it should not be directly attributed to the 2018 0823 tropical depression event without event matching."
        if mailiao_2018_month != 8
        else "- The peak month is August; event attribution still requires checking timing against the 2018 0823 tropical depression event."
    )

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
        "## Summary Statistics",
        "",
        summary_statistics.to_markdown(index=False),
        "",
        "## Monthly Mean Tide IQR Outliers",
        "",
        monthly_outliers.to_markdown(index=False) if not monthly_outliers.empty else "No monthly IQR outliers detected.",
        "",
        "## Incomplete Monthly Records",
        "",
        incomplete_monthly_records.to_markdown(index=False)
        if not incomplete_monthly_records.empty
        else "No incomplete monthly records flagged.",
        "",
        "## Valid Monthly Record Counts",
        "",
        valid_month_counts.to_markdown(index=False),
        "",
        (
            "Mailiao 2015 Jan-Jul records are flagged as partial or incomplete monthly records "
            "because several key monthly tide statistics are missing. Therefore, these months are "
            "excluded from the QC version of monthly mean tide and seasonality plots, but the "
            "original data are retained for transparency."
        ),
        "",
        "## Annual High-Water IQR Outliers",
        "",
        annual_outliers.to_markdown(index=False) if not annual_outliers.empty else "No annual IQR outliers detected.",
        "",
        "## Top Five Annual Extreme High-Water Years",
        "",
        top_extremes.to_markdown(index=False),
        "",
        "## Mailiao 2018 Monthly Check",
        "",
        mailiao_2018_monthly_check.to_markdown(index=False),
        "",
        (
            "Mailiao 2018 annual maximum high-water level is contributed by "
            f"month {mailiao_2018_month}: "
            f"highest_high_water_level = {mailiao_2018_peak['highest_high_water_level']:.3f} m, "
            f"highest_astronomical_tide = {mailiao_2018_peak['highest_astronomical_tide']:.3f} m, "
            f"hhw_minus_hat = {mailiao_2018_peak['hhw_minus_hat']:.3f} m."
        ),
        "",
        not_august_note,
        "",
        "## Trend Results",
        "",
        trend_results.to_markdown(index=False),
        "",
        "## Trend-Based Sensitivity Scenario",
        "",
        trend_sensitivity.to_markdown(index=False),
        "",
        (
            "This trend-based sensitivity scenario assumes the observed linear Sen's slope "
            "continues for 10, 25, and 50 years. It illustrates possible background "
            "relative water-level increases and should not be interpreted as a precise forecast "
            "or a replacement for extreme-value uncertainty analysis."
        ),
        "",
        "## Extreme-Value Model Fit",
        "",
        model_metrics.to_markdown(index=False),
        "",
        (
            "Histogram bin edges were manually selected using interpretable water-level intervals. "
            "For Mailiao, 0.5 m intervals were used to highlight the isolated 2018 extreme event. "
            "For Boziliao, narrower intervals were used because annual maximum high-water levels "
            "were concentrated within a smaller range. The histograms are used for visual inspection "
            "only; model assessment relies on AIC/BIC, Q-Q plots, return level plots, and sensitivity analysis."
        ),
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
        "## Data Quality Notes",
        "",
        "- Raw monthly figures are retained for transparency and data-quality inspection. QC-filtered monthly figures exclude Mailiao Jan-Jul 2015 partial/incomplete records and are used as the main figures for monthly mean tide and seasonality interpretation.",
        "- The QC-filtered monthly time series keeps the full monthly date index and sets Mailiao Jan-Jul 2015 mean tide levels to NaN, so the missing period appears as a line gap without interpolation or filling.",
        "- Monthly-mean and seasonality figures use QC-filtered data, while annual-extreme analyses retain the original annual maximum records.",
        "- The HHW-HAT plot highlights Mailiao 2018 as an influential extreme year.",
        "- Return level plots with log x-axis are recommended for hydrologic frequency interpretation.",
        "- Annual Mean Sea Level Trend uses the official annual `mean_tide_level` from `annual_tide_yunlin.csv`, so it retains the original annual data rather than recalculating from monthly records.",
        "- Mailiao has abnormal monthly mean tide values around 2015 and they are flagged for QC in `monthly_outliers.csv`.",
        "- Mailiao 2015 Jan-Jul monthly records are flagged as partial or incomplete and are excluded from QC monthly EDA figures.",
        "- Mailiao 2018 has a dominant annual maximum high-water value and strongly affects tail fitting.",
        "- Outliers are flagged for review only; they are not removed from the analysis.",
        "",
        "## Interpretation Notes",
        "",
        "- Trends should be interpreted as relative sea-level change, not direct global sea-level rise.",
        "- Trends represent relative sea-level change referenced to TWVD2001.",
        "- The annual maximum high-water level includes astronomical and meteorological effects.",
        "- `hhw_minus_hat` is a preliminary indicator of non-astronomical contribution, not a rigorous storm surge decomposition.",
        "- With only 20 years of data, 50- and 100-year return levels have high uncertainty.",
        "- 50-year and 100-year return levels are extrapolations and have high uncertainty.",
        "- GEV is flexible, but its shape parameter may be unstable for short records.",
        "- GEV results should be interpreted as a sensitivity comparison rather than a definitive design estimate.",
        "- Gumbel should be treated as the more stable baseline model.",
        "- Gumbel is treated as the stable baseline model, while GEV is interpreted as a sensitivity model due to possible shape-parameter instability under the short 20-year record.",
        "- Mailiao's 2018 extreme high-water value can noticeably affect tail fitting and should be discussed as an influential event.",
        "- Mailiao's monthly mean tide around 2015 should be checked as a potential data-quality issue before strong physical interpretation.",
        "- The two tide stations support comparison along the Yunlin coast but do not fully represent the entire coastline.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def analyze() -> None:
    ensure_directories()
    configure_plots()
    station_info, annual_tide, monthly_tide = load_processed_data()

    plot_eda(monthly_tide, annual_tide)
    monthly_outliers, annual_outliers = write_outlier_tables(monthly_tide, annual_tide)
    incomplete_monthly_records = write_incomplete_monthly_records(monthly_tide)
    valid_month_counts = write_valid_month_counts(monthly_tide)
    plot_monthly_outliers(monthly_tide, monthly_outliers)
    top_extremes = write_top_extreme_years(annual_tide)
    mailiao_2018_monthly_check = write_mailiao_2018_monthly_check(monthly_tide)
    summary_statistics = write_summary_statistics(annual_tide)
    trend_results = run_trend_analysis(annual_tide)
    trend_sensitivity = run_trend_based_sensitivity(trend_results)
    _, model_metrics, return_levels = run_extreme_value_analysis(annual_tide)
    distribution_comparison, return_levels_all = run_all_distribution_analysis(annual_tide)
    extreme_sensitivity = run_extreme_year_sensitivity(annual_tide)
    length_sensitivity = run_data_length_sensitivity(annual_tide)
    write_summary(
        station_info,
        summary_statistics,
        monthly_outliers,
        incomplete_monthly_records,
        valid_month_counts,
        annual_outliers,
        top_extremes,
        mailiao_2018_monthly_check,
        trend_results,
        trend_sensitivity,
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
