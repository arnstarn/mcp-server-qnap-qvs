#!/bin/sh
# Start both the MCP server and the config UI

LOG_FILE="${LOG_FILE:-/config/mcp-qvs.log}"

# Start config UI in background
mcp-qvs-config-ui &

# Start MCP server, tee output to log file
exec mcp-server-qnap-qvs 2>&1 | tee -a "$LOG_FILE"
