"""
Mini Azure Storage MCP Server

A stdio MCP server that exposes a single tool to upload a local file
to an Azure Blob Storage container under a chosen subfolder path.
"""

import os
import asyncio
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError


app = Server("mini-azurestorage-mcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="upload_file",
            description=(
                "Upload a local file to an Azure Blob Storage container. "
                "The blob name is formed by joining the optional subfolder "
                "and the file name, e.g. 'subfolder/filename.txt'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "local_file_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the local file to upload.",
                    },
                    "container_name": {
                        "type": "string",
                        "description": "Name of the Azure Blob Storage container.",
                    },
                    "subfolder": {
                        "type": "string",
                        "description": (
                            "Optional subfolder (virtual path prefix) inside the container. "
                            "Leave empty to upload directly to the container root."
                        ),
                        "default": "",
                    },
                    "blob_name": {
                        "type": "string",
                        "description": (
                            "Optional name for the blob. "
                            "Defaults to the file's base name."
                        ),
                        "default": "",
                    },
                },
                "required": ["local_file_path", "container_name"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "upload_file":
        raise ValueError(f"Unknown tool: {name}")

    local_file_path = arguments.get("local_file_path", "")
    container_name = arguments.get("container_name", "")
    subfolder = arguments.get("subfolder", "").strip("/")
    blob_name = arguments.get("blob_name", "").strip("/")

    if not local_file_path:
        return [types.TextContent(type="text", text="Error: 'local_file_path' is required.")]
    if not container_name:
        return [types.TextContent(type="text", text="Error: 'container_name' is required.")]

    file_path = Path(local_file_path)
    if not file_path.exists():
        return [types.TextContent(type="text", text=f"Error: File not found: {local_file_path}")]
    if not file_path.is_file():
        return [types.TextContent(type="text", text=f"Error: Path is not a file: {local_file_path}")]

    if not blob_name:
        blob_name = file_path.name

    full_blob_name = f"{subfolder}/{blob_name}" if subfolder else blob_name

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not connection_string:
        return [
            types.TextContent(
                type="text",
                text=(
                    "Error: Environment variable 'AZURE_STORAGE_CONNECTION_STRING' is not set. "
                    "Please set it to your Azure Storage connection string."
                ),
            )
        ]

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        url = blob_client.url
        return [
            types.TextContent(
                type="text",
                text=f"File uploaded successfully.\nBlob: {full_blob_name}\nURL: {url}",
            )
        ]
    except AzureError as exc:
        return [types.TextContent(type="text", text=f"Azure error: {exc}")]
    except OSError as exc:
        return [types.TextContent(type="text", text=f"File read error: {exc}")]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
