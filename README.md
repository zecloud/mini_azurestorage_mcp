# mini-azurestorage-mcp

A **stdio MCP server** (built with the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)) that exposes one tool for uploading a local file to an **Azure Blob Storage** container under a chosen subfolder.

## Requirements

- Python ≥ 3.10
- An Azure Storage account and its connection string

## Installation

```bash
pip install -e .
```

Or install the dependencies directly:

```bash
pip install mcp>=1.27.0 azure-storage-blob>=12.28.0
```

## Configuration

Set the connection string as an environment variable before running the server:

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
```

## Running the server

```bash
python server.py
# or, after installing the package:
mini-azurestorage-mcp
```

The server communicates over **stdio** and is compatible with any MCP client (e.g. Claude Desktop, VS Code Copilot, etc.).

## Tool: `upload_file`

Uploads a local file to an Azure Blob Storage container.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `local_file_path` | string | ✅ | Absolute or relative path to the local file |
| `container_name` | string | ✅ | Name of the target Azure Blob Storage container |
| `subfolder` | string | ➖ | Virtual path prefix inside the container (default: `""`) |
| `blob_name` | string | ➖ | Name for the blob (default: the file's base name) |

### Example

```json
{
  "tool": "upload_file",
  "arguments": {
    "local_file_path": "/home/user/report.pdf",
    "container_name": "my-container",
    "subfolder": "reports/2024"
  }
}
```

The file will be stored as `reports/2024/report.pdf` inside `my-container`.

## MCP client configuration (Claude Desktop example)

```json
{
  "mcpServers": {
    "azurestorage": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "AZURE_STORAGE_CONNECTION_STRING": "<your-connection-string>"
      }
    }
  }
}
```