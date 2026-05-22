from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

TARGET_STATION_NAMES = {"麥寮潮位站", "萡子寮潮位站"}
EXPECTED_START_YEAR = 2006
EXPECTED_END_YEAR = 2025
EXPECTED_YEAR_COUNT = EXPECTED_END_YEAR - EXPECTED_START_YEAR + 1

TIDE_FIELD_MAP = {
    "HighestHighWaterLevel": "highest_high_water_level",
    "HighestAstronomicalTide": "highest_astronomical_tide",
    "MeanHighWaterLevel": "mean_high_water_level",
    "MeanTideLevel": "mean_tide_level",
    "MeanLowWaterLevel": "mean_low_water_level",
    "LowestAstronomicalTide": "lowest_astronomical_tide",
    "LowestLowWaterLevel": "lowest_low_water_level",
    "MeanTidalRange": "mean_tidal_range",
    "MaxAstronomicalTidalRange": "max_astronomical_tidal_range",
    "MeanHighWaterOfSpringTide": "mean_high_water_of_spring_tide",
    "MeanLowWaterOfSpringTide": "mean_low_water_of_spring_tide",
}

TIDE_COLUMNS = list(TIDE_FIELD_MAP.values())


def ensure_directories() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def find_input_json() -> Path:
    """Prefer the planned raw-data location, but support the current root copy."""
    candidates = [
        RAW_DIR / "C-B0052-001.json",
        ROOT / "C-B0052-001.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Cannot find C-B0052-001.json. Put it in data/raw/C-B0052-001.json."
    )


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_numeric(value: Any) -> float:
    """Convert CWA numeric strings to float while preserving '-' as missing."""
    if value in (None, "", "-"):
        return np.nan
    if isinstance(value, list):
        value = value[0] if value else np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def clean_int(value: Any) -> int:
    if isinstance(value, list):
        value = value[0] if value else value
    return int(value)


def extract_locations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locations = (
        payload.get("cwaopendata", {})
        .get("Resources", {})
        .get("Resource", {})
        .get("Data", {})
        .get("SeaSurfaceObs", {})
        .get("Location", [])
    )
    return as_list(locations)


def station_info_row(station: dict[str, Any], stats_block: dict[str, Any]) -> dict[str, Any]:
    county = station.get("County", {}) or {}
    town = station.get("Town", {}) or {}
    return {
        "station_id": station.get("StationID"),
        "station_name": station.get("StationName"),
        "station_name_en": station.get("StationNameEN"),
        "county": county.get("CountyName"),
        "town": town.get("TownName"),
        "latitude": clean_numeric(station.get("StationLatitude")),
        "longitude": clean_numeric(station.get("StationLongitude")),
        "datum": station.get("Description"),
        "start_year": clean_int(stats_block.get("StartYear")),
        "end_year": clean_int(stats_block.get("EndYear")),
    }


def tide_values(record: dict[str, Any]) -> dict[str, float]:
    return {
        output_name: clean_numeric(record.get(input_name))
        for input_name, output_name in TIDE_FIELD_MAP.items()
    }


def normalize_annual_records(
    annual_records: list[dict[str, Any]],
    years: list[int],
    station_name: str,
) -> list[dict[str, Any]]:
    """Skip the first CWA annual summary row when present."""
    if len(annual_records) == len(years) + 1:
        return annual_records[1:]
    if len(annual_records) == len(years):
        return annual_records
    raise ValueError(
        f"{station_name}: Annual length mismatch. "
        f"Got {len(annual_records)}, expected {len(years)} or {len(years) + 1}."
    )


def normalize_monthly_records(
    monthly_records: list[dict[str, Any]],
    years: list[int],
    station_name: str,
) -> list[dict[str, Any]]:
    """Skip the first 12 CWA monthly climatology rows when present."""
    expected_month_count = len(years) * 12
    if len(monthly_records) == expected_month_count + 12:
        return monthly_records[12:]
    if len(monthly_records) == expected_month_count:
        return monthly_records
    raise ValueError(
        f"{station_name}: Monthly length mismatch. "
        f"Got {len(monthly_records)}, expected {expected_month_count} "
        f"or {expected_month_count + 12}."
    )


def annual_rows(
    station: dict[str, Any],
    stats_block: dict[str, Any],
    years: list[int],
) -> list[dict[str, Any]]:
    station_name = station.get("StationName")
    annual_records = normalize_annual_records(
        as_list(stats_block.get("Annual")),
        years,
        station_name,
    )

    rows = []
    for year, record in zip(years, annual_records, strict=True):
        row = {
            "station_id": station.get("StationID"),
            "station_name": station_name,
            "year": year,
        }
        row.update(tide_values(record))
        rows.append(row)
    return rows


def monthly_rows(
    station: dict[str, Any],
    stats_block: dict[str, Any],
    years: list[int],
) -> list[dict[str, Any]]:
    station_name = station.get("StationName")
    monthly_records = normalize_monthly_records(
        as_list(stats_block.get("Monthly")),
        years,
        station_name,
    )

    rows = []
    for index, record in enumerate(monthly_records):
        year = years[index // 12]
        month = clean_int(record.get("DataMonth", (index % 12) + 1))
        row = {
            "station_id": station.get("StationID"),
            "station_name": station_name,
            "year": year,
            "month": month,
            "date": f"{year:04d}-{month:02d}-01",
        }
        row.update(tide_values(record))
        rows.append(row)
    return rows


def add_hhw_minus_hat(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["hhw_minus_hat"] = (
        data["highest_high_water_level"] - data["highest_astronomical_tide"]
    )
    return data


def validate_outputs(
    station_info: pd.DataFrame,
    annual_tide: pd.DataFrame,
    monthly_tide: pd.DataFrame,
) -> None:
    if len(station_info) != 2:
        raise ValueError(f"station_info should have 2 rows, got {len(station_info)}.")
    if len(annual_tide) != 40:
        raise ValueError(f"annual_tide should have 40 rows, got {len(annual_tide)}.")
    if len(monthly_tide) != 480:
        raise ValueError(f"monthly_tide should have 480 rows, got {len(monthly_tide)}.")

    for station_name in TARGET_STATION_NAMES:
        annual_station = annual_tide[annual_tide["station_name"] == station_name]
        monthly_station = monthly_tide[monthly_tide["station_name"] == station_name]
        annual_years = annual_station["year"].tolist()

        if annual_years != list(range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1)):
            raise ValueError(f"{station_name}: expected years 2006-2025, got {annual_years}.")
        if len(monthly_station) != 240:
            raise ValueError(f"{station_name}: monthly rows should be 240.")

    for frame_name, frame in {
        "annual_tide": annual_tide,
        "monthly_tide": monthly_tide,
    }.items():
        for column in ["mean_tide_level", "highest_high_water_level", "hhw_minus_hat"]:
            if not pd.api.types.is_float_dtype(frame[column]):
                raise TypeError(f"{frame_name}.{column} should be float.")


def process() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_directories()
    input_path = find_input_json()

    with input_path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)

    station_rows = []
    annual_records = []
    monthly_records = []

    for location in extract_locations(payload):
        station = location.get("Station", {}) or {}
        station_name = station.get("StationName")
        if station_name not in TARGET_STATION_NAMES:
            continue

        stats_block = location.get("StationObsStatistics", {}) or {}
        years = [clean_int(year) for year in as_list(stats_block.get("DataYear"))]
        if len(years) != EXPECTED_YEAR_COUNT:
            raise ValueError(
                f"{station_name}: expected 20 years from 2006-2025, got {len(years)}."
            )

        station_rows.append(station_info_row(station, stats_block))
        annual_records.extend(annual_rows(station, stats_block, years))
        monthly_records.extend(monthly_rows(station, stats_block, years))

    station_info = pd.DataFrame(station_rows).sort_values("station_id")
    annual_tide = add_hhw_minus_hat(pd.DataFrame(annual_records))
    monthly_tide = add_hhw_minus_hat(pd.DataFrame(monthly_records))
    monthly_tide["date"] = pd.to_datetime(monthly_tide["date"])

    validate_outputs(station_info, annual_tide, monthly_tide)

    station_info.to_csv(
        PROCESSED_DIR / "station_info_yunlin_tide.csv",
        index=False,
        encoding="utf-8-sig",
    )
    annual_tide.to_csv(
        PROCESSED_DIR / "annual_tide_yunlin.csv",
        index=False,
        encoding="utf-8-sig",
    )
    monthly_tide.to_csv(
        PROCESSED_DIR / "monthly_tide_yunlin.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Input: {input_path}")
    print(f"station_info: {len(station_info)} rows")
    print(f"annual_tide: {len(annual_tide)} rows")
    print(f"monthly_tide: {len(monthly_tide)} rows")
    return station_info, annual_tide, monthly_tide


if __name__ == "__main__":
    process()
