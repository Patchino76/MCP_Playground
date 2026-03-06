"""
tools/report_tools.py — MCP tools for saving charts and writing reports
========================================================================
Two tools:
  - list_output_files     : List all files in the output/ directory
  - write_markdown_report : Write a Markdown report file to output/

These tools let the Reporter agent assemble a final deliverable.
"""

import json
import os

from mcp import types

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── list_output_files ─────────────────────────────────────────────────────────

list_output_files_input_schema = {
    "type": "object",
    "properties": {
        "extension_filter": {
            "type": "string",
            "description": "Optional file extension filter, e.g. 'png' or 'md'. Leave empty for all files.",
        },
    },
    "required": [],
}

list_output_files_tool = types.Tool(
    name="list_output_files",
    description=(
        "List all files currently in the output/ directory. "
        "Optionally filter by file extension (e.g. 'png' for charts, 'md' for reports). "
        "Returns file names and sizes."
    ),
    inputSchema=list_output_files_input_schema,
)


async def list_output_files(arguments: dict) -> list[types.TextContent]:
    ext_filter = arguments.get("extension_filter", "").strip().lower()

    if not os.path.exists(OUTPUT_DIR):
        return [types.TextContent(type="text", text=json.dumps({"files": [], "count": 0}))]

    files = []
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if ext_filter and not f.lower().endswith(f".{ext_filter}"):
            continue
        full_path = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(full_path):
            files.append({
                "name": f,
                "size_kb": round(os.path.getsize(full_path) / 1024, 1),
            })

    result = {"count": len(files), "files": files}
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ── write_markdown_report ─────────────────────────────────────────────────────

write_markdown_report_input_schema = {
    "type": "object",
    "properties": {
        "filename": {
            "type": "string",
            "description": "Name for the report file (e.g. 'analysis_report.md'). Saved to output/ folder.",
        },
        "content": {
            "type": "string",
            "description": (
                "Full Markdown content of the report. Use standard Markdown with headings, "
                "bullet points, tables, and image references like ![title](chart_name.png). "
                "Image paths should be relative (just the filename, since images are in the same folder)."
            ),
        },
    },
    "required": ["filename", "content"],
}

write_markdown_report_tool = types.Tool(
    name="write_markdown_report",
    description=(
        "Write a Markdown report file to the output/ directory. "
        "Use this to create the final analysis report with embedded chart references, "
        "statistical summaries, conclusions, and recommendations. "
        "Charts saved by execute_python can be referenced as ![title](filename.png)."
    ),
    inputSchema=write_markdown_report_input_schema,
)


async def write_markdown_report(arguments: dict) -> list[types.TextContent]:
    filename = arguments.get("filename", "").strip()
    content = arguments.get("content", "").strip()

    if not filename:
        raise ValueError("filename is required")
    if not content:
        raise ValueError("content is required")

    if not filename.endswith(".md"):
        filename += ".md"

    file_path = os.path.join(OUTPUT_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    result = {
        "status": "written",
        "file": filename,
        "path": file_path,
        "size_kb": round(os.path.getsize(file_path) / 1024, 1),
        "lines": content.count("\n") + 1,
    }
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
