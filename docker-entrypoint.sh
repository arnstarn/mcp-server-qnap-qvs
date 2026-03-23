#!/bin/sh
# Start both the MCP server and the config UI
# Handles graceful shutdown of both processes

LOG_FILE="${LOG_FILE:-/config/mcp-qvs.log}"

# Trap signals to clean up both processes
cleanup() {
    echo "Shutting down..."
    kill $UI_PID $MCP_PID 2>/dev/null
    wait $UI_PID $MCP_PID 2>/dev/null
    exit 0
}
trap cleanup TERM INT QUIT

# Start config UI in background
mcp-qvs-config-ui &
UI_PID=$!

# Start MCP server in background, tee to log
mcp-server-qnap-qvs 2>&1 | tee -a "$LOG_FILE" &
MCP_PID=$!

# Wait for either process to exit
wait -n $UI_PID $MCP_PID 2>/dev/null || wait $MCP_PID
cleanup
