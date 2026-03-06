"""
tools/python_executor.py — MCP tool for executing Python code
==============================================================
One tool:
  - execute_python : Run arbitrary Python code with access to the loaded
                     dataframe, numpy, pandas, seaborn, and matplotlib.

The code runs in a restricted namespace that pre-injects:
  - df       : the currently loaded dataframe
  - pd       : pandas
  - np       : numpy
  - sns      : seaborn
  - plt      : matplotlib.pyplot
  - OUTPUT_DIR : path to the output/ folder for saving charts

Returns stdout, any saved figure paths, and the last expression value.

Security note: This is a DEMO tool. In production you would sandbox execution.
"""

import io
import json
import os
import sys
import traceback

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from mcp import types

from tools.data_tools import get_dataframe

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── execute_python ────────────────────────────────────────────────────────────

execute_python_input_schema = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": (
                "Python code to execute. The code has access to: "
                "df (loaded dataframe), pd, np, sns, plt, and OUTPUT_DIR. "
                "To save charts, use plt.savefig(os.path.join(OUTPUT_DIR, 'filename.png'), dpi=150, bbox_inches='tight') "
                "then plt.close(). Print results to stdout for the agent to see."
            ),
        },
    },
    "required": ["code"],
}

execute_python_tool = types.Tool(
    name="execute_python",
    description=(
        "Execute Python code for data analysis. The code runs with access to the "
        "loaded dataframe as 'df', plus pandas (pd), numpy (np), seaborn (sns), "
        "matplotlib.pyplot (plt), and OUTPUT_DIR for saving charts. "
        "Print any results you want to capture. Save charts to OUTPUT_DIR. "
        "Returns stdout output, list of saved chart files, and any errors."
    ),
    inputSchema=execute_python_input_schema,
)


async def execute_python(arguments: dict) -> list[types.TextContent]:
    code = arguments.get("code", "").strip()
    if not code:
        raise ValueError("code is required")

    df = get_dataframe()
    if df is None:
        raise ValueError("No dataframe loaded. Call load_csv first.")

    # Track which files exist before execution
    existing_files = set(os.listdir(OUTPUT_DIR)) if os.path.exists(OUTPUT_DIR) else set()

    # Build execution namespace
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "sns": sns,
        "plt": plt,
        "os": os,
        "OUTPUT_DIR": OUTPUT_DIR,
        "__builtins__": __builtins__,
    }

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_stdout = io.StringIO()

    error_msg = None
    try:
        exec(code, namespace)
    except Exception:
        error_msg = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        # Ensure all figures are closed to free memory
        plt.close("all")

    stdout_output = captured_stdout.getvalue()

    # Detect newly created files
    current_files = set(os.listdir(OUTPUT_DIR)) if os.path.exists(OUTPUT_DIR) else set()
    new_files = sorted(current_files - existing_files)

    result: dict = {
        "stdout": stdout_output[:5000] if stdout_output else "",
        "new_files": new_files,
    }
    if error_msg:
        result["error"] = error_msg[:3000]

    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
