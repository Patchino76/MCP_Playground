from tools.data_tools import (
    load_csv_tool, load_csv,
    get_dataframe_info_tool, get_dataframe_info,
)
from tools.python_executor import (
    execute_python_tool, execute_python,
)
from tools.report_tools import (
    list_output_files_tool, list_output_files,
    write_markdown_report_tool, write_markdown_report,
)

# Registry mapping tool name -> {"tool": types.Tool, "handler": callable}
# To add a new tool: create its descriptor + handler in the appropriate file,
# then add one entry here. server.py and client.py need zero changes.
tools = {
    load_csv_tool.name:              {"tool": load_csv_tool,              "handler": load_csv},
    get_dataframe_info_tool.name:    {"tool": get_dataframe_info_tool,    "handler": get_dataframe_info},
    execute_python_tool.name:        {"tool": execute_python_tool,        "handler": execute_python},
    list_output_files_tool.name:     {"tool": list_output_files_tool,     "handler": list_output_files},
    write_markdown_report_tool.name: {"tool": write_markdown_report_tool, "handler": write_markdown_report},
}
