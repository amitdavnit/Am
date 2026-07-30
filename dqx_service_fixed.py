from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import ast
import re

import pandas as pd


def _get_spark():
    """Return active Spark session when running in Databricks."""
    try:
        from pyspark.sql import SparkSession
        return SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    except Exception:
        return None


def _demo_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, None],
            "email": [
                "amit@example.com",
                "invalid-email",
                "user@example.com",
                None,
                "test@example.com",
            ],
            "age": [28, 35, -2, 46, 150],
            "country_code": ["IN", "US", "IN", None, "UK"],
        }
    )


def load_table(catalog: str, schema: str, table: str, limit: int = 10000):
    """
    Load a Databricks table as Spark DataFrame.
    Falls back to a demo pandas DataFrame outside Databricks.
    """
    spark = _get_spark()
    full_name = f"`{catalog}`.`{schema}`.`{table}`"
    if spark is not None:
        return spark.table(full_name).limit(limit), full_name
    return _demo_dataframe(), "demo.local.customer_data"


def list_catalogs() -> List[str]:
    spark = _get_spark()
    if spark is None:
        return ["demo"]
    return [r["catalog"] for r in spark.sql("SHOW CATALOGS").collect()]


def list_schemas(catalog: str) -> List[str]:
    spark = _get_spark()
    if spark is None:
        return ["local"]
    rows = spark.sql(f"SHOW SCHEMAS IN `{catalog}`").collect()
    key = "databaseName" if rows and "databaseName" in rows[0].asDict() else "namespace"
    return [r.asDict().get(key) for r in rows if r.asDict().get(key)]


def list_tables(catalog: str, schema: str) -> List[str]:
    spark = _get_spark()
    if spark is None:
        return ["customer_data"]
    rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema}`").collect()
    return [r["tableName"] for r in rows]


def run_profiling(catalog: str, schema: str, table: str) -> Dict[str, Any]:
    df, full_name = load_table(catalog, schema, table)

    if hasattr(df, "toPandas"):
        pdf = df.toPandas()
    else:
        pdf = df.copy()

    columns = []
    row_count = len(pdf)

    for col in pdf.columns:
        series = pdf[col]
        non_null = int(series.notna().sum())
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))

        column_info = {
            "column": col,
            "dtype": str(series.dtype),
            "row_count": row_count,
            "non_null_count": non_null,
            "null_count": null_count,
            "null_percentage": round((null_count / row_count * 100), 2) if row_count else 0,
            "unique_count": unique_count,
            "sample_values": [str(x) for x in series.dropna().head(5).tolist()],
        }

        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            column_info["min"] = float(clean.min()) if not clean.empty else None
            column_info["max"] = float(clean.max()) if not clean.empty else None

        columns.append(column_info)

    duplicate_count = int(pdf.duplicated().sum())

    return {
        "table_name": full_name,
        "row_count": row_count,
        "column_count": len(pdf.columns),
        "duplicate_count": duplicate_count,
        "columns": columns,
    }


def generate_rules(profile_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generic rule suggestion logic.
    This can later be replaced with Databricks Labs DQX rule generation.
    """
    rules: List[Dict[str, Any]] = []

    for col in profile_result.get("columns", []):
        name = col["column"]
        dtype = col["dtype"].lower()
        null_pct = col.get("null_percentage", 0)

        # Suggest not-null for low-null columns and common identifier columns.
        if null_pct <= 5 or name.lower().endswith("_id"):
            rules.append(
                {
                    "rule_id": f"{name}_not_null",
                    "column": name,
                    "rule_type": "not_null",
                    "description": f"{name} should not be null",
                    "enabled": True,
                    "parameters": {},
                }
            )

        if "email" in name.lower():
            rules.append(
                {
                    "rule_id": f"{name}_email_format",
                    "column": name,
                    "rule_type": "regex",
                    "description": f"{name} should contain a valid email address",
                    "enabled": True,
                    "parameters": {
                        "pattern": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
                    },
                }
            )

        if pd.api.types.is_numeric_dtype(pd.Series(dtype=dtype)):
            # dtype-string check above is not always reliable; name heuristic covers common fields.
            pass

        if any(k in name.lower() for k in ["age", "amount", "score", "quantity"]):
            observed_min = col.get("min")
            observed_max = col.get("max")
            min_value = 0 if observed_min is None or observed_min < 0 else observed_min
            max_value = 120 if "age" in name.lower() else observed_max
            rules.append(
                {
                    "rule_id": f"{name}_range",
                    "column": name,
                    "rule_type": "range",
                    "description": f"{name} should be within the accepted range",
                    "enabled": True,
                    "parameters": {
                        "min": min_value,
                        "max": max_value,
                    },
                }
            )

    return rules


def execute_rules(
    catalog: str,
    schema: str,
    table: str,
    rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    df, full_name = load_table(catalog, schema, table)

    if hasattr(df, "toPandas"):
        pdf = df.toPandas()
    else:
        pdf = df.copy()

    failed_rows = []
    rule_summary = []

    for rule in rules:
        if not rule.get("enabled", True):
            continue

        column = rule["column"]
        rule_type = rule["rule_type"]
        params = rule.get("parameters", {})

        if isinstance(params, str):
            try:
                parsed_params = ast.literal_eval(params)
                params = parsed_params if isinstance(parsed_params, dict) else {}
            except (ValueError, SyntaxError):
                params = {}

        failure_mask = pd.Series(False, index=pdf.index)

        if column not in pdf.columns:
            failure_mask = pd.Series(True, index=pdf.index)
        elif rule_type == "not_null":
            failure_mask = pdf[column].isna()
        elif rule_type == "regex":
            pattern = params.get("pattern", ".*")
            failure_mask = ~pdf[column].fillna("").astype(str).str.match(pattern)
        elif rule_type == "range":
            min_v = params.get("min")
            max_v = params.get("max")
            numeric = pd.to_numeric(pdf[column], errors="coerce")
            failure_mask = numeric.isna()
            if min_v is not None:
                failure_mask = failure_mask | (numeric < float(min_v))
            if max_v is not None:
                failure_mask = failure_mask | (numeric > float(max_v))

        failed_count = int(failure_mask.sum())
        rule_summary.append(
            {
                "rule_id": rule["rule_id"],
                "column": column,
                "rule_type": rule_type,
                "failed_count": failed_count,
                "passed_count": int(len(pdf) - failed_count),
            }
        )

        for idx in pdf.index[failure_mask]:
            failed_rows.append(
                {
                    "row_index": int(idx),
                    "rule_id": rule["rule_id"],
                    "column": column,
                    "failed_value": None if pd.isna(pdf.at[idx, column]) else str(pdf.at[idx, column]),
                    "error": rule["description"],
                }
            )

    failed_row_indexes = {x["row_index"] for x in failed_rows}
    invalid_count = len(failed_row_indexes)
    valid_count = len(pdf) - invalid_count

    return {
        "table_name": full_name,
        "total_records": len(pdf),
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "passed_percentage": round(valid_count / len(pdf) * 100, 2) if len(pdf) else 0,
        "rule_summary": rule_summary,
        "failed_records": failed_rows,
    }
