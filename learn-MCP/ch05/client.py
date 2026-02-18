from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession
import asyncio
from typing import Optional, Dict, Any, List
import mcp.types as types

from mcp.types import (LoggingMessageNotificationParams, TextContent)
from mcp.shared.session import RequestResponder

port = 8000

async def message_handler(
    message: RequestResponder[types.ServerRequestType, types.ClientResult]
    | types.ServerNotification | Exception
) -> None:
    print("Message:", message)
    if isinstance(message, Exception):
        print("Exception:", message)


async def main() -> None:
    async with streamable_http_client(f"http://localhost:{port}/mcp") as (
        read_stream,
        write_stream,
        session_callback,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
            message_handler=message_handler,
        ) as session:
            await session.initialize()

            results = []
            tool_result = await session.call_tool(
                "echo",
                {"message": "Hello, world!"},
            )
            print("Tool result:", tool_result)
            results.append(tool_result)

            tool_csv = await session.call_tool(
                "process_csv",
                {"file": "test.csv"},
            )
            print("Tool result:", tool_csv)
            results.append(tool_csv)
            
        
asyncio.run(main())
