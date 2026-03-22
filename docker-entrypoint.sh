#!/bin/sh
# Start both the MCP server and the config UI

# Start config UI in background
mcp-qvs-config-ui &

# Start MCP server in foreground
exec mcp-server-qnap-qvs
