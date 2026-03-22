FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# SSE mode by default when running in Docker
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8445
ENV QNAP_HOST=""
ENV QNAP_PORT=443
ENV QNAP_USERNAME=""
ENV QNAP_PASSWORD=""
ENV QNAP_VERIFY_SSL=false

EXPOSE 8445

ENTRYPOINT ["mcp-server-qnap-qvs"]
