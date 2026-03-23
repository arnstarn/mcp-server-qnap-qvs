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
APP_PROXY="/etc/app_proxy.conf"
PROXY_PATH="/mcp-qvs"

# Read optional Docker registry credentials from .env
docker_login() {
    if [ -f "${ENV_FILE}" ]; then
        REGISTRY=$(grep '^DOCKER_REGISTRY=' "${ENV_FILE}" | cut -d= -f2-)
        USERNAME=$(grep '^DOCKER_USERNAME=' "${ENV_FILE}" | cut -d= -f2-)
        PASSWORD=$(grep '^DOCKER_PASSWORD=' "${ENV_FILE}" | cut -d= -f2-)
        if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
            echo "Logging into registry ${REGISTRY:-ghcr.io}..."
            echo "$PASSWORD" | $DOCKER login "${REGISTRY:-ghcr.io}" -u "$USERNAME" --password-stdin 2>/dev/null
        fi
    fi
}

# Get the configured image name
get_image() {
    if [ -f "${ENV_FILE}" ]; then
        IMG=$(grep '^DOCKER_IMAGE=' "${ENV_FILE}" | cut -d= -f2-)
    fi
    REGISTRY=$(grep '^DOCKER_REGISTRY=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2-)
    echo "${REGISTRY:-ghcr.io}/${IMG:-arnstarn/mcp-server-qnap-qvs:latest}"
}

# Set up HTTPS reverse proxy via QNAP's apache_proxy
setup_proxy() {
    # Write our proxy rules to /etc/app_proxy.conf
    # (included by both apache-sys-proxy.conf and apache-sys-proxy-ssl.conf)
    cat > "${APP_PROXY}" << EOF
ProxyPass ${PROXY_PATH} http://127.0.0.1:8446/ retry=0
ProxyPassReverse ${PROXY_PATH} http://127.0.0.1:8446/
EOF
    # Graceful reload of the proxy Apache processes
    /usr/local/apache/bin/apache_proxy -k graceful -f /etc/apache-sys-proxy.conf 2>/dev/null
    /usr/local/apache/bin/apache_proxys -k graceful -f /etc/apache-sys-proxy-ssl.conf 2>/dev/null
    echo "HTTPS proxy: https://$(hostname)${PROXY_PATH}/"
}

# Remove HTTPS reverse proxy
remove_proxy() {
    > "${APP_PROXY}" 2>/dev/null
    /usr/local/apache/bin/apache_proxy -k graceful -f /etc/apache-sys-proxy.conf 2>/dev/null
    /usr/local/apache/bin/apache_proxys -k graceful -f /etc/apache-sys-proxy-ssl.conf 2>/dev/null
}

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
            echo "Open the app to configure credentials."
            exit 1
        fi
        echo "Starting ${QPKG_NAME}..."
        docker_login
        IMAGE=$(get_image)
        $DOCKER pull "$IMAGE" 2>/dev/null || echo "Pull failed — using cached image"
        cd "${QPKG_DIR}" && $COMPOSE -f "${COMPOSE_FILE}" up -d

        # Set up HTTPS proxy for config UI
        setup_proxy

        # Sync QPKG version in App Center
        NEW_VER=$($DOCKER exec $QPKG_NAME python3 -c "from mcp_server_qnap_qvs import __version__; print(__version__)" 2>/dev/null)
        if [ -n "$NEW_VER" ]; then
            CUR_VER=$(getcfg $QPKG_NAME Version -f $CONF)
            if [ "$NEW_VER" != "$CUR_VER" ]; then
                /sbin/setcfg $QPKG_NAME Version "$NEW_VER" -f $CONF
                echo "Updated QPKG version: $CUR_VER -> $NEW_VER"
            fi
        fi
        ;;
    stop)
        echo "Stopping ${QPKG_NAME}..."
        remove_proxy
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
