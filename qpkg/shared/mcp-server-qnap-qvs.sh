#!/bin/sh
# Service script for mcp-server-qnap-qvs QPKG

CONF=/etc/config/qpkg.conf
QPKG_NAME="mcp-server-qnap-qvs"
QPKG_DIR=$(getcfg $QPKG_NAME Install_Path -f $CONF)
CS_DIR=$(getcfg container-station Install_Path -f $CONF)
DOCKER="${CS_DIR}/bin/docker"
COMPOSE="$DOCKER compose"
COMPOSE_FILE="${QPKG_DIR}/docker-compose.yml"
ENV_FILE="${QPKG_DIR}/.env"

case "$1" in
    start)
        ENABLED=$(getcfg $QPKG_NAME Enable -u -d FALSE -f $CONF)
        if [ "$ENABLED" != "TRUE" ]; then
            echo "$QPKG_NAME is disabled."
            exit 1
        fi
        if [ ! -x "$DOCKER" ]; then
            echo "ERROR: Docker not found. Install Container Station first."
            exit 1
        fi
        if [ ! -f "${ENV_FILE}" ]; then
            echo "ERROR: ${ENV_FILE} not found."
            echo "Copy .env.example to .env and configure your QNAP credentials."
            exit 1
        fi
        echo "Starting ${QPKG_NAME}..."
        $DOCKER pull ghcr.io/arnstarn/mcp-server-qnap-qvs:latest 2>/dev/null
        cd "${QPKG_DIR}" && $COMPOSE -f "${COMPOSE_FILE}" up -d
        ;;
    stop)
        echo "Stopping ${QPKG_NAME}..."
        cd "${QPKG_DIR}" && $COMPOSE -f "${COMPOSE_FILE}" down 2>/dev/null
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        cd "${QPKG_DIR}" && $COMPOSE -f "${COMPOSE_FILE}" ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
