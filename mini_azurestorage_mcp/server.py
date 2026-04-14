"""
Mini Azure Storage MCP Server

A stdio MCP server that exposes a single tool to upload a local file
to an Azure Blob Storage container under a chosen subfolder path.
"""

import logging
import os
import asyncio
import threading
from pathlib import Path
from typing import Any, NoReturn

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

logger = logging.getLogger("mini-azurestorage-mcp")

app = Server("mini-azurestorage-mcp")

_blob_service_client: BlobServiceClient | None = None
_cached_connection_string: str = ""
_client_lock = threading.Lock()


def _get_blob_service_client() -> BlobServiceClient | None:
    """Return a cached BlobServiceClient, recreating it only when the connection string changes."""
    global _blob_service_client, _cached_connection_string
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not connection_string:
        return None
    with _client_lock:
        if _blob_service_client is None or connection_string != _cached_connection_string:
            _blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            _cached_connection_string = connection_string
    return _blob_service_client


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
                    "overwrite": {
                        "type": "boolean",
                        "description": (
                            "Whether to overwrite the blob if it already exists. "
                            "Defaults to true."
                        ),
                        "default": True,
                    },
                },
                "required": ["local_file_path", "container_name"],
            },
        )
    ]


def _error(message: str) -> NoReturn:
    """Raise so the MCP SDK wraps the message in a CallToolResult with isError=True."""
    raise ValueError(message)


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name != "upload_file":
        _error(f"Unsupported tool: {name}")

    local_file_path = arguments.get("local_file_path", "")
    container_name = arguments.get("container_name", "")
    subfolder = arguments.get("subfolder", "").strip("/")
    blob_name = arguments.get("blob_name", "").strip("/")
    overwrite = arguments.get("overwrite", True)

    if not local_file_path:
        _error("'local_file_path' is required.")
    if not container_name:
        _error("'container_name' is required.")

    # Resolve to absolute path to prevent path traversal confusion
    file_path = Path(local_file_path).resolve()
    if not file_path.exists():
        _error(f"File not found: {file_path}")
    if not file_path.is_file():
        _error(f"Path is not a file: {file_path}")

    if not blob_name:
        blob_name = file_path.name

    full_blob_name = f"{subfolder}/{blob_name}" if subfolder else blob_name

    # Validate connection string and build client before entering upload try block
    try:
        blob_service_client = _get_blob_service_client()
    except ValueError as exc:
        _error(f"Invalid connection string: {exc}")

    if blob_service_client is None:
        _error(
            "Environment variable 'AZURE_STORAGE_CONNECTION_STRING' is not set. "
            "Please set it to your Azure Storage connection string."
        )

    try:
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        def _do_upload() -> str:
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=overwrite)
            return blob_client.url

        url = await asyncio.to_thread(_do_upload)
        logger.info("Uploaded %s → %s", file_path, full_blob_name)
        return [
            types.TextContent(
                type="text",
                text=f"File uploaded successfully.\nBlob: {full_blob_name}\nURL: {url}",
            )
        ]
    except AzureError as exc:
        logger.error("Azure error uploading %s: %s", file_path, exc)
        _error(f"Azure error: {exc}")
    except OSError as exc:
        logger.error("File read error for %s: %s", file_path, exc)
        _error(f"File read error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error uploading %s", file_path)
        _error(f"Unexpected error: {exc}")


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
