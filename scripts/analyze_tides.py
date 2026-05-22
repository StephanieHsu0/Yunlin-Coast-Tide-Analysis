from __future__ import annotations

import math
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"

RETURN_PERIODS = [10, 20, 50, 100]
MIN_MONTHS_FOR_ANNUAL_MEAN = 10


STATION_ALIASES = {
    "麥寮": "Mailiao",
    "麦寮": "Mailiao",
    "mailiao": "Mailiao",
    "MAILIAO": "Mailiao",
    "泊子寮": "Boziliao",
    "萡子寮": "Boziliao",
    "boziliao": "Boziliao",
    "bozihlia": "Boziliao",
    "BOZILIAO": "Boziliao",
}


COLUMN_ALIASES = {
    "station": [
        "station",
        "station_name",
        "site",
        "測站",
        "測站名稱",
        "站名",
        "潮位站",
        "觀測站",
    ],
    "year": ["year", "yr", "年份", "年"],
    "month": ["month", "mon", "月份", "月"],
    "mean_tide": [
        "mean_tide",
        "monthly_mean_tide",
        "mean sea level",
        "mean_sea_level",
        "平均潮位",
        "月平均潮位",
        "平均水位",
        "平均海平面",
    ],
    "max_high_water": [
        "max_high_water",
        "maximum_high_water",
        "annual_max_high_water",
        "highest_high_water",
        "最高高潮位",
        "最高高潮暴潮位",
        "最高水位",
        "最高高潮",
    ],
    "max_astronomical_tide": [
        "max_astronomical_tide",
        "highest_astronomical_tide",
        "最高天文潮",
    ],
    "min_low_water": [
        "min_low_water",
        "lowest_low_water",
        "最低低潮位",
        "最低低潮",
        "最低水位",
    ],
    "tide_datum": ["tide_datum", "datum", "潮位基準", "潮高基準", "基準"],
    "unit": ["unit", "單位"],
    "latitude": ["latitude", "lat", "緯度"],
    "longitude": ["longitude", "lon", "lng", "經度"],
}


@dataclass
class FitResult:
    station: str
    distribution: str
    params: tuple[float, ...]
    log_likelihood: float
    aic: float
    bic: float


def ensure_directories() -> None:
    for directory in [RAW_DIR, PROCESSED_DIR, FIG_DIR, TABLE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def normalize_header(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", "_", text)
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip("_").lower()


def find_column(columns: list[str], canonical: str) -> str | None:
    normalized = {normalize_header(col): col for col in columns}
    aliases = [normalize_header(item) for item in COLUMN_ALIASES[canonical]]

    for alias in aliases:
        if alias in normalized:
            return normalized[alias]

    for norm_col, original_col in normalized.items():
        if any(alias and alias in norm_col for alias in aliases):
            return original_col

    return None


def infer_station_from_text(text: str) -> str | None:
    lower_text = text.lower()
    for alias, canonical in STATION_ALIASES.items():
        if alias.lower() in lower_text:
            return canonical
    return None


def standardize_station(value: object, fallback: str | None = None) -> str:
    if pd.isna(value):
        return fallback or "Unknown"

    text = str(value).strip()
    inferred = infer_station_from_text(text)
    if inferred:
        return inferred
    return text or fallback or "Unknown"


def scalar(value: object) -> object:
    if isinstance(value, list):
        return value[0] if value else np.nan
    return value


def read_cwa_json(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)

    locations = (
        payload.get("cwaopendata", {})
        .get("Resources", {})
        .get("Resource", {})
        .get("Data", {})
        .get("SeaSurfaceObs", {})
        .get("Location", [])
    )
    if isinstance(locations, dict):
        locations = [locations]

    rows = []
    for location in locations:
        station_info = location.get("Station", {})
        station_name = station_info.get("StationName", "")
        station_name_en = station_info.get("StationNameEN", "")
        station = infer_station_from_text(f"{station_name} {station_name_en}")
        if station not in {"Mailiao", "Boziliao"}:
            continue

        statistics_block = location.get("StationObsStatistics", {})
        years = [int(year) for year in statistics_block.get("DataYear", [])]
        monthly_records = statistics_block.get("Monthly", [])
        if isinstance(monthly_records, dict):
            monthly_records = [monthly_records]

        for index, record in enumerate(monthly_records):
            if not years:
                continue
            year_index = min(index // 12, len(years) - 1)
            year = years[year_index]

            rows.append(
                {
                    "station": station,
                    "year": year,
                    "month": scalar(record.get("DataMonth")),
                    "mean_tide": scalar(record.get("MeanTideLevel")),
                    "max_high_water": scalar(record.get("HighestHighWaterLevel")),
                    "max_astronomical_tide": scalar(record.get("HighestAstronomicalTide")),
                    "min_low_water": scalar(record.get("LowestLowWaterLevel")),
                    "tide_datum": station_info.get("Description", ""),
                    "unit": "m",
                    "latitude": station_info.get("StationLatitude"),
                    "longitude": station_info.get("StationLongitude"),
                    "source_file": path.name,
                }
            )

    if not rows:
        raise ValueError(f"No Mailiao or Boziliao records found in {path.name}.")
    return pd.DataFrame(rows)


def read_raw_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".json":
        return read_cwa_json(path)

    if path.suffix.lower() == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp950")

    if path.suffix.lower() in {".xlsx", ".xls"}:
        frames = pd.read_excel(path, sheet_name=None)
        return pd.concat(
            [frame.assign(source_sheet=sheet) for sheet, frame in frames.items()],
            ignore_index=True,
        )

    raise ValueError(f"Unsupported file type: {path}")


def write_template() -> None:
    template = pd.DataFrame(
        {
            "station": ["Mailiao", "Mailiao", "Boziliao", "Boziliao"],
            "year": [2020, 2020, 2020, 2020],
            "month": [1, 2, 1, 2],
            "mean_tide": [np.nan, np.nan, np.nan, np.nan],
            "max_high_water": [np.nan, np.nan, np.nan, np.nan],
            "max_astronomical_tide": [np.nan, np.nan, np.nan, np.nan],
            "min_low_water": [np.nan, np.nan, np.nan, np.nan],
            "tide_datum": ["TWVD2001", "TWVD2001", "TWVD2001", "TWVD2001"],
            "unit": ["m", "m", "m", "m"],
        }
    )
    template.to_csv(RAW_DIR / "tide_data_template.csv", index=False, encoding="utf-8-sig")

    requirements = pd.DataFrame(
        {
            "required_field": ["station", "year", "month", "mean_tide", "max_high_water"],
            "purpose": [
                "Compare Mailiao and Boziliao",
                "Annual trend and annual maxima",
                "Seasonality and annual aggregation",
                "Monthly and annual mean sea-level analysis",
                "Annual maximum series for extreme-value analysis",
            ],
        }
    )
    requirements.to_csv(TABLE_DIR / "data_requirements.csv", index=False, encoding="utf-8-sig")


def load_and_clean_data() -> pd.DataFrame:
    candidate_files = list(RAW_DIR.iterdir()) + list(ROOT.glob("*.json"))
    files = sorted(
        {
            path
            for path in candidate_files
            if path.suffix.lower() in {".csv", ".xlsx", ".xls", ".json"}
            and path.name != "tide_data_template.csv"
        }
    )

    if not files:
        write_template()
        raise FileNotFoundError(
            f"No CWA data files found in {RAW_DIR}. A template was created."
        )

    cleaned_frames = []
    for path in files:
        frame = read_raw_file(path)
        frame = frame.dropna(how="all")
        if frame.empty:
            continue

        selected: dict[str, pd.Series | str | float] = {}
        fallback_station = infer_station_from_text(path.stem)

        for canonical in COLUMN_ALIASES:
            column = find_column(list(frame.columns), canonical)
            if column is not None:
                selected[canonical] = frame[column]

        if "station" not in selected:
            selected["station"] = fallback_station or path.stem

        missing = [col for col in ["year", "month", "mean_tide", "max_high_water"] if col not in selected]
        if missing:
            raise ValueError(
                f"{path.name} is missing required columns: {missing}. "
                "Rename columns or use the template format."
            )

        standardized = pd.DataFrame(selected)
        standardized["source_file"] = path.name
        cleaned_frames.append(standardized)

    if not cleaned_frames:
        write_template()
        raise ValueError("Raw files were found, but no usable rows were detected.")

    data = pd.concat(cleaned_frames, ignore_index=True)
    data["station"] = [
        standardize_station(value, infer_station_from_text(str(source)))
        for value, source in zip(data["station"], data["source_file"])
    ]

    for column in [
        "year",
        "month",
        "mean_tide",
        "max_high_water",
        "max_astronomical_tide",
        "min_low_water",
        "latitude",
        "longitude",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    data["year"] = data["year"].astype("Int64")
    data["month"] = data["month"].astype("Int64")
    data = data.dropna(subset=["station", "year", "month"])
    data = data[(data["month"] >= 1) & (data["month"] <= 12)]
    data = data.sort_values(["station", "year", "month"]).reset_index(drop=True)

    data.to_csv(PROCESSED_DIR / "monthly_tide_clean.csv", index=False, encoding="utf-8-sig")
    return data


def build_quality_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    summary = (
        monthly.groupby(["station", "year"])
        .agg(
            valid_months=("mean_tide", lambda values: values.notna().sum()),
            valid_max_high_water_months=("max_high_water", lambda values: values.notna().sum()),
            missing_months=("month", lambda values: 12 - values.nunique()),
            mean_tide_missing=("mean_tide", lambda values: values.isna().sum()),
            max_high_water_missing=("max_high_water", lambda values: values.isna().sum()),
        )
        .reset_index()
    )
    summary["annual_mean_status"] = np.where(
        summary["valid_months"] >= MIN_MONTHS_FOR_ANNUAL_MEAN,
        "usable",
        np.where(summary["valid_months"] >= 6, "incomplete", "exclude"),
    )
    summary.to_csv(PROCESSED_DIR / "data_quality_summary.csv", index=False, encoding="utf-8-sig")
    return summary


def build_annual_datasets(monthly: pd.DataFrame, quality: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual_mean = (
        monthly.groupby(["station", "year"])
        .agg(
            annual_mean_sea_level=("mean_tide", "mean"),
            valid_months=("mean_tide", lambda values: values.notna().sum()),
        )
        .reset_index()
    )
    annual_mean = annual_mean[annual_mean["valid_months"] >= MIN_MONTHS_FOR_ANNUAL_MEAN]

    annual_max = (
        monthly.groupby(["station", "year"])
        .agg(
            annual_max_high_water=("max_high_water", "max"),
            valid_max_high_water_months=("max_high_water", lambda values: values.notna().sum()),
        )
        .reset_index()
    )
    annual_max = annual_max[annual_max["valid_max_high_water_months"] >= 10]
    annual_max = annual_max.dropna(subset=["annual_max_high_water"])

    annual_mean.to_csv(PROCESSED_DIR / "annual_mean_sea_level.csv", index=False, encoding="utf-8-sig")
    annual_max.to_csv(PROCESSED_DIR / "annual_max_high_water.csv", index=False, encoding="utf-8-sig")
    return annual_mean, annual_max


def save_fig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIG_DIR / name, dpi=300, bbox_inches="tight")
    plt.close()


def plot_eda(monthly: pd.DataFrame, annual_mean: pd.DataFrame, annual_max: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid")

    plot_data = monthly.copy()
    plot_data["date"] = pd.to_datetime(
        {"year": plot_data["year"].astype(int), "month": plot_data["month"].astype(int), "day": 1}
    )

    plt.figure(figsize=(11, 5))
    sns.lineplot(data=plot_data, x="date", y="mean_tide", hue="station", marker="o")
    plt.title("Monthly Mean Tide Level")
    plt.xlabel("Date")
    plt.ylabel("Monthly mean tide level")
    save_fig("01_monthly_mean_tide_timeseries.png")

    plt.figure(figsize=(10, 5))
    sns.boxplot(data=plot_data, x="month", y="mean_tide", hue="station")
    plt.title("Seasonality of Monthly Mean Tide")
    plt.xlabel("Month")
    plt.ylabel("Monthly mean tide level")
    save_fig("02_monthly_tide_boxplot.png")

    plt.figure(figsize=(10, 5))
    sns.lineplot(data=annual_mean, x="year", y="annual_mean_sea_level", hue="station", marker="o")
    plt.title("Annual Mean Sea Level")
    plt.xlabel("Year")
    plt.ylabel("Annual mean sea level")
    save_fig("03_annual_mean_sea_level.png")

    plt.figure(figsize=(10, 5))
    sns.lineplot(data=annual_max, x="year", y="annual_max_high_water", hue="station", marker="o")
    plt.title("Annual Maximum High-Water Level")
    plt.xlabel("Year")
    plt.ylabel("Annual maximum high-water level")
    save_fig("04_annual_max_high_water.png")


def mann_kendall_test(values: np.ndarray) -> tuple[float, float, float]:
    n = len(values)
    s = 0
    for i in range(n - 1):
        s += np.sign(values[i + 1 :] - values[i]).sum()

    unique_values, counts = np.unique(values, return_counts=True)
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

    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            slopes.append((values[j] - values[i]) / (j - i))
    sen_slope = float(np.median(slopes)) if slopes else np.nan
    return float(s), float(p_value), sen_slope


def run_trend_analysis(annual_mean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    trend_plot = annual_mean.copy()

    plt.figure(figsize=(10, 5))
    for station, group in annual_mean.groupby("station"):
        group = group.dropna(subset=["annual_mean_sea_level"]).sort_values("year")
        if len(group) < 3:
            continue

        x = group["year"].astype(float).to_numpy()
        y = group["annual_mean_sea_level"].astype(float).to_numpy()
        reg = stats.linregress(x, y)
        mk_s, mk_p, sen = mann_kendall_test(y)

        rows.append(
            {
                "station": station,
                "n_years": len(group),
                "linear_slope_m_per_year": reg.slope,
                "linear_slope_mm_per_year": reg.slope * 1000,
                "linear_p_value": reg.pvalue,
                "r_squared": reg.rvalue**2,
                "mk_statistic_s": mk_s,
                "mk_p_value": mk_p,
                "sen_slope_m_per_year": sen,
                "sen_slope_mm_per_year": sen * 1000,
                "conclusion": "significant increasing"
                if reg.slope > 0 and mk_p < 0.05
                else "significant decreasing"
                if reg.slope < 0 and mk_p < 0.05
                else "not significant",
            }
        )

        plt.scatter(x, y, label=f"{station} observed")
        plt.plot(x, reg.intercept + reg.slope * x, label=f"{station} trend")

    plt.title("Annual Mean Sea Level Trend")
    plt.xlabel("Year")
    plt.ylabel("Annual mean sea level")
    plt.legend()
    save_fig("05_annual_mean_trend.png")

    result = pd.DataFrame(rows)
    result.to_csv(TABLE_DIR / "trend_results.csv", index=False, encoding="utf-8-sig")
    return result


def fit_distribution(values: np.ndarray, station: str, distribution: str) -> FitResult:
    if distribution == "Gumbel":
        params = stats.gumbel_r.fit(values)
        logpdf = stats.gumbel_r.logpdf(values, *params)
    elif distribution == "GEV":
        params = stats.genextreme.fit(values)
        logpdf = stats.genextreme.logpdf(values, *params)
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    log_likelihood = float(np.sum(logpdf))
    k = len(params)
    n = len(values)
    aic = 2 * k - 2 * log_likelihood
    bic = k * math.log(n) - 2 * log_likelihood
    return FitResult(station, distribution, tuple(float(p) for p in params), log_likelihood, aic, bic)


def distribution_ppf(probabilities: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.ppf(probabilities, *fit.params)
    return stats.genextreme.ppf(probabilities, *fit.params)


def distribution_pdf(x: np.ndarray, fit: FitResult) -> np.ndarray:
    if fit.distribution == "Gumbel":
        return stats.gumbel_r.pdf(x, *fit.params)
    return stats.genextreme.pdf(x, *fit.params)


def run_extreme_value_analysis(annual_max: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fit_rows = []
    metric_rows = []
    return_rows = []

    for station, group in annual_max.groupby("station"):
        values = group["annual_max_high_water"].dropna().astype(float).to_numpy()
        values = np.sort(values)
        if len(values) < 8:
            warnings.warn(f"{station}: fewer than 8 annual maxima; skipping extreme-value fitting.")
            continue

        fits = [fit_distribution(values, station, "Gumbel"), fit_distribution(values, station, "GEV")]

        for fit in fits:
            row = {
                "station": station,
                "distribution": fit.distribution,
                "log_likelihood": fit.log_likelihood,
                "aic": fit.aic,
                "bic": fit.bic,
            }
            if fit.distribution == "Gumbel":
                row.update({"location": fit.params[0], "scale": fit.params[1], "shape": np.nan})
            else:
                row.update({"shape": fit.params[0], "location": fit.params[1], "scale": fit.params[2]})
            fit_rows.append(row)
            metric_rows.append(
                {
                    "station": station,
                    "distribution": fit.distribution,
                    "aic": fit.aic,
                    "bic": fit.bic,
                    "n": len(values),
                }
            )

            for return_period in RETURN_PERIODS:
                probability = 1 - 1 / return_period
                return_rows.append(
                    {
                        "station": station,
                        "distribution": fit.distribution,
                        "return_period_years": return_period,
                        "annual_exceedance_probability": 1 / return_period,
                        "return_level": distribution_ppf(np.array([probability]), fit)[0],
                    }
                )

        x_grid = np.linspace(values.min() - values.std(), values.max() + values.std(), 300)
        plt.figure(figsize=(9, 5))
        sns.histplot(values, stat="density", bins="auto", color="lightgray", edgecolor="black")
        for fit in fits:
            plt.plot(x_grid, distribution_pdf(x_grid, fit), label=fit.distribution)
        plt.title(f"{station}: Annual Maximum High-Water Distribution")
        plt.xlabel("Annual maximum high-water level")
        plt.ylabel("Density")
        plt.legend()
        save_fig(f"06_{station.lower()}_histogram_fitted_pdf.png")

        probabilities = (np.arange(1, len(values) + 1) - 0.5) / len(values)
        plt.figure(figsize=(6, 6))
        for fit in fits:
            theoretical = distribution_ppf(probabilities, fit)
            plt.scatter(theoretical, values, label=fit.distribution)
        min_value = min(values.min(), *(distribution_ppf(probabilities, fit).min() for fit in fits))
        max_value = max(values.max(), *(distribution_ppf(probabilities, fit).max() for fit in fits))
        plt.plot([min_value, max_value], [min_value, max_value], color="black", linestyle="--")
        plt.title(f"{station}: Q-Q Plot")
        plt.xlabel("Theoretical quantiles")
        plt.ylabel("Observed annual maxima")
        plt.legend()
        save_fig(f"07_{station.lower()}_qq_plot.png")

        return_period_grid = np.arange(2, 101)
        plt.figure(figsize=(8, 5))
        for fit in fits:
            probabilities_grid = 1 - 1 / return_period_grid
            levels = distribution_ppf(probabilities_grid, fit)
            plt.plot(return_period_grid, levels, label=fit.distribution)
        plt.scatter(np.ones_like(values) * np.nan, values)
        plt.title(f"{station}: Return Level Plot")
        plt.xlabel("Return period (years)")
        plt.ylabel("Return level")
        plt.legend()
        save_fig(f"08_{station.lower()}_return_level.png")

    fit_table = pd.DataFrame(fit_rows)
    metric_table = pd.DataFrame(metric_rows)
    return_table = pd.DataFrame(return_rows)

    fit_table.to_csv(TABLE_DIR / "extreme_value_parameters.csv", index=False, encoding="utf-8-sig")
    metric_table.to_csv(TABLE_DIR / "model_fit_metrics.csv", index=False, encoding="utf-8-sig")
    return_table.to_csv(TABLE_DIR / "return_levels.csv", index=False, encoding="utf-8-sig")
    return fit_table, metric_table, return_table


def run_sensitivity_analysis(annual_mean: pd.DataFrame, annual_max: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    extreme_rows = []
    length_rows = []

    for station, group in annual_max.groupby("station"):
        group = group.dropna(subset=["annual_max_high_water"]).sort_values("year")
        if len(group) < 10:
            continue

        original_values = group["annual_max_high_water"].astype(float).to_numpy()
        max_idx = int(np.argmax(original_values))
        reduced_values = np.delete(original_values, max_idx)
        removed_year = int(group.iloc[max_idx]["year"])

        for label, values in [("all_years", original_values), ("remove_largest_year", reduced_values)]:
            for distribution in ["Gumbel", "GEV"]:
                fit = fit_distribution(values, station, distribution)
                for return_period in [50, 100]:
                    extreme_rows.append(
                        {
                            "station": station,
                            "scenario": label,
                            "removed_year": removed_year if label == "remove_largest_year" else np.nan,
                            "distribution": distribution,
                            "return_period_years": return_period,
                            "return_level": distribution_ppf(np.array([1 - 1 / return_period]), fit)[0],
                        }
                    )

        for recent_years in [10, 15]:
            recent = group.tail(recent_years)
            if len(recent) < 8:
                continue
            for distribution in ["Gumbel", "GEV"]:
                fit = fit_distribution(recent["annual_max_high_water"].astype(float).to_numpy(), station, distribution)
                length_rows.append(
                    {
                        "station": station,
                        "period": f"last_{recent_years}_years",
                        "distribution": distribution,
                        "n_years": len(recent),
                        "return_level_50yr": distribution_ppf(np.array([1 - 1 / 50]), fit)[0],
                        "return_level_100yr": distribution_ppf(np.array([1 - 1 / 100]), fit)[0],
                    }
                )

    extreme_table = pd.DataFrame(extreme_rows)
    length_table = pd.DataFrame(length_rows)
    extreme_table.to_csv(TABLE_DIR / "sensitivity_extreme_year.csv", index=False, encoding="utf-8-sig")
    length_table.to_csv(TABLE_DIR / "sensitivity_data_length.csv", index=False, encoding="utf-8-sig")

    if not extreme_table.empty:
        plt.figure(figsize=(9, 5))
        sns.barplot(
            data=extreme_table[extreme_table["return_period_years"] == 50],
            x="station",
            y="return_level",
            hue="scenario",
        )
        plt.title("50-Year Return Level Sensitivity to Largest Extreme Year")
        plt.xlabel("Station")
        plt.ylabel("Return level")
        save_fig("09_extreme_year_sensitivity.png")

    return extreme_table, length_table


def write_analysis_summary(
    monthly: pd.DataFrame,
    quality: pd.DataFrame,
    trend: pd.DataFrame,
    metrics: pd.DataFrame,
    return_levels: pd.DataFrame,
) -> None:
    lines = [
        "# Analysis Summary",
        "",
        "This file is generated by `scripts/analyze_tides.py`.",
        "",
        "## Data Coverage",
        "",
    ]

    coverage = (
        monthly.groupby("station")
        .agg(start_year=("year", "min"), end_year=("year", "max"), n_rows=("year", "size"))
        .reset_index()
    )
    lines.append(coverage.to_markdown(index=False))
    lines.append("")
    lines.append("## Trend Results")
    lines.append("")
    lines.append(trend.to_markdown(index=False) if not trend.empty else "Not enough annual mean data.")
    lines.append("")
    lines.append("## Model Fit Metrics")
    lines.append("")
    lines.append(metrics.to_markdown(index=False) if not metrics.empty else "Not enough annual maximum data.")
    lines.append("")
    lines.append("## Return Levels")
    lines.append("")
    lines.append(return_levels.to_markdown(index=False) if not return_levels.empty else "Not enough annual maximum data.")
    lines.append("")
    lines.append("## Interpretation Reminders")
    lines.extend(
        [
            "",
            "- Interpret tide-gauge trend as relative sea-level change.",
            "- High return-period estimates are uncertain when the record length is short.",
            "- Observed high water includes tide and meteorological effects unless components are separated.",
            "- Two stations support comparison but cannot fully represent all Yunlin coastal variability.",
        ]
    )

    (ROOT / "outputs" / "analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_directories()

    try:
        monthly = load_and_clean_data()
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        print(f"Template written to: {RAW_DIR / 'tide_data_template.csv'}")
        return

    quality = build_quality_summary(monthly)
    annual_mean, annual_max = build_annual_datasets(monthly, quality)

    if not monthly.empty and not annual_mean.empty and not annual_max.empty:
        plot_eda(monthly, annual_mean, annual_max)

    trend = run_trend_analysis(annual_mean) if not annual_mean.empty else pd.DataFrame()
    fit_table, metrics, return_levels = run_extreme_value_analysis(annual_max) if not annual_max.empty else (
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )
    run_sensitivity_analysis(annual_mean, annual_max)
    write_analysis_summary(monthly, quality, trend, metrics, return_levels)

    print("Analysis complete.")
    print(f"Processed data: {PROCESSED_DIR}")
    print(f"Figures: {FIG_DIR}")
    print(f"Tables: {TABLE_DIR}")


if __name__ == "__main__":
    main()
