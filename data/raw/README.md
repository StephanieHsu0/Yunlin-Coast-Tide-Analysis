# Raw Data

Put original CWA tide gauge statistics files in this folder.

Recommended files:

- Mailiao tide station monthly statistics
- Boziliao tide station monthly statistics

Accepted formats:

- `.csv`
- `.xlsx`
- `.xls`

The analysis script will try to infer column names from Chinese or English headers. If automatic detection fails, rename the important columns to:

```text
station, year, month, mean_tide, max_high_water
```

Optional columns:

```text
max_astronomical_tide, min_low_water, tide_datum, unit, latitude, longitude
```
