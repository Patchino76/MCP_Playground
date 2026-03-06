from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("Streamable demo")

@mcp.tool(description = "A simpletool returning file content")
async def echo(message: str, ctx: Context) -> str:
    await ctx.info((f"Processng  1/3:"))
    await ctx.info((f"Processng 2/3:"))
    await ctx.info((f"Processng  3/3:"))

    return f"here is the file content: {message}"

@mcp.tool(description="CSV provessing tool")
async def process_csv(file: str, ctx: Context) -> str:
    await ctx.info((f"Processng file 1/3:"))
    await ctx.info((f"Processng file 2/3:"))
    await ctx.info((f"Processng file 3/3:"))

    return f"here is the file content: {file}"

mcp.run(transport="streamable-http")