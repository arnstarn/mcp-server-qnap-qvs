FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY docker-entrypoint.sh ./

RUN pip install --no-cache-dir . && chmod +x docker-entrypoint.sh

# SSE mode by default when running in Docker
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8445
ENV CONFIG_UI_PORT=8446
ENV ENV_FILE=/config/.env
ENV QNAP_HOST=""
ENV QNAP_PORT=443
ENV QNAP_USERNAME=""
ENV QNAP_PASSWORD=""
ENV QNAP_VERIFY_SSL=false

EXPOSE 8445 8446

VOLUME /config

ENTRYPOINT ["./docker-entrypoint.sh"]
