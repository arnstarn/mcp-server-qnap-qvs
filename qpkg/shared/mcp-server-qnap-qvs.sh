#!/bin/sh
# Service script for mcp-server-qnap-qvs QPKG
# Manages the Docker container via docker-compose

QPKG_NAME="mcp-server-qnap-qvs"
QPKG_DIR="/share/CACHEDEV1_DATA/.qpkg/${QPKG_NAME}"
COMPOSE_FILE="${QPKG_DIR}/docker-compose.yml"
ENV_FILE="${QPKG_DIR}/.env"

case "$1" in
    start)
        echo "Starting ${QPKG_NAME}..."
        if [ ! -f "${ENV_FILE}" ]; then
            echo "ERROR: ${ENV_FILE} not found. Please configure credentials first."
            exit 1
        fi
        cd "${QPKG_DIR}" && docker-compose -f "${COMPOSE_FILE}" up -d
        ;;
    stop)
        echo "Stopping ${QPKG_NAME}..."
        cd "${QPKG_DIR}" && docker-compose -f "${COMPOSE_FILE}" down
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        docker-compose -f "${COMPOSE_FILE}" ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
