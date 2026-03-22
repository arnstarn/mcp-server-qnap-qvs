# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT open a public GitHub issue**
2. Open a [private security advisory](https://github.com/arnstarn/mcp-server-qnap-qvs/security/advisories/new) on this repo
3. Include details of the vulnerability and steps to reproduce

I will respond within 72 hours and work with you on a fix.

## Security Considerations

### Credentials

This MCP server connects to your QNAP NAS using admin credentials. Keep these safe:

- **Never commit `.env` files** — `.env` is in `.gitignore` by default
- **Use environment variables** for credentials, not config files
- **Restrict network access** to the MCP server when running in SSE mode

### Self-Signed TLS

QNAP NAS devices commonly use self-signed certificates. The `QNAP_VERIFY_SSL=false` setting
disables certificate verification. If you have a valid TLS certificate on your NAS, set
`QNAP_VERIFY_SSL=true`.

### Destructive Operations

All write operations (shutdown, delete, reset, etc.) require `confirm=true` as a safety guard.
The MCP client (Claude) must explicitly confirm before any destructive action is executed.
