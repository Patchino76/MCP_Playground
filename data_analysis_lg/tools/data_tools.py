"""
tools/data_tools.py — MCP tools for loading and inspecting CSV data
====================================================================
Two tools:
  - load_csv          : Load a CSV file into the server's in-memory store
  - get_dataframe_info: Return shape, dtypes, nulls, and basic stats

These follow the same low-level MCP pattern as lg_mcp_01/tools/tickets.py:
  1. inputSchema dict  (JSON Schema)
  2. types.Tool        (MCP descriptor)
  3. async handler     (does the work, returns TextContent)
"""

import json
import os
from typing import Any

import pandas as pd
from mcp import types

# ── In-memory dataframe store ─────────────────────────────────────────────────
# Shared across all tools in this server process.
_dataframes: dict[str, pd.DataFrame] = {}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_dataframe(name: str = "default") -> pd.DataFrame | None:
    return _dataframes.get(name)


def set_dataframe(df: pd.DataFrame, name: str = "default") -> None:
    _dataframes[name] = df


# ── load_csv ──────────────────────────────────────────────────────────────────

load_csv_input_schema = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": (
                "Path to the CSV file, relative to the project csv/ folder "
                "(e.g. 'example_data.csv') or an absolute path."
            ),
        },
        "nrows": {
            "type": "integer",
            "description": "Optional: max rows to load. Omit to load all rows.",
        },
    },
    "required": ["file_path"],
}

load_csv_tool = types.Tool(
    name="load_csv",
    description=(
        "Load a CSV file into the server's in-memory dataframe store. "
        "Returns the shape, column names, and first 5 rows as confirmation. "
        "The loaded data is then available for all subsequent analysis tools."
    ),
    inputSchema=load_csv_input_schema,
)


async def load_csv(arguments: dict) -> list[types.TextContent]:
    file_path = arguments.get("file_path", "").strip()
    nrows = arguments.get("nrows", 0)

    if not file_path:
        raise ValueError("file_path is required")

    # Resolve relative paths against the csv/ folder
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, "csv", file_path)

    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    read_kwargs: dict[str, Any] = {}
    if nrows and nrows > 0:
        read_kwargs["nrows"] = nrows

    df = pd.read_csv(file_path, **read_kwargs)

    # Auto-parse timestamp columns
    for col in df.columns:
        if "time" in col.lower() or "date" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

    set_dataframe(df)

    result = {
        "status": "loaded",
        "file": os.path.basename(file_path),
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "columns": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
        "head_2_rows": df.head(2).to_dict(orient="records"),
    }
    # Convert any Timestamps to strings for JSON serialization
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ── get_dataframe_info ────────────────────────────────────────────────────────

get_dataframe_info_input_schema = {
    "type": "object",
    "properties": {
        "include_stats": {
            "type": "string",
            "description": "Set to 'yes' to include descriptive statistics (mean, std, min, max, quartiles). Default 'no'.",
        },
    },
    "required": [],
}

get_dataframe_info_tool = types.Tool(
    name="get_dataframe_info",
    description=(
        "Return detailed info about the currently loaded dataframe: "
        "shape, column names, data types, null counts, memory usage, "
        "and optionally descriptive statistics. Call load_csv first."
    ),
    inputSchema=get_dataframe_info_input_schema,
)


async def get_dataframe_info(arguments: dict) -> list[types.TextContent]:
    df = get_dataframe()
    if df is None:
        raise ValueError("No dataframe loaded. Call load_csv first.")

    include_stats = arguments.get("include_stats", "no").lower() == "yes"

    # Build compact info to stay within token limits
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]
    null_counts = {col: int(df[col].isnull().sum()) for col in df.columns if df[col].isnull().sum() > 0}

    info: dict[str, Any] = {
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "numeric_columns": numeric_cols,
        "non_numeric_columns": non_numeric_cols,
        "columns_with_nulls": null_counts if null_counts else "none",
    }

    if include_stats and numeric_cols:
        desc = df[numeric_cols].describe().round(2)
        info["stats_summary"] = desc.to_dict()

    return [types.TextContent(type="text", text=json.dumps(info, indent=2, default=str))]
