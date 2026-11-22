# Deploy: Streamable HTTP behind a bearer token

`zepp-mcp` speaks stdio. This stack wraps it with `mcp-proxy` (Streamable HTTP at `/mcp`) and puts Caddy in front: `/healthz` is open, everything else needs `Authorization: Bearer <token>`, otherwise 401. The server container publishes no port and runs as a non-root user on a read-only root filesystem with all capabilities dropped. No Zepp password is stored; the token cache lives in the `zepp-token` volume (file mode 600).

## Setup

```bash
# 1. Bearer token, root-only, outside the repository
install -d -m 700 /etc/zepp-mcp
umask 077; printf 'MCP_BEARER_TOKEN=%s\n' "$(openssl rand -hex 32)" > /etc/zepp-mcp/bearer.env

# 2. Optional: run the test suite on Linux
docker build -f deploy/Dockerfile --target test .

# 3. Build and start (BEARER_ENV_FILE defaults to /etc/zepp-mcp/bearer.env)
docker compose -f deploy/compose.yaml up -d --build

# 4. One interactive Zepp login (password via getpass, one attempt, only the token is kept)
docker compose -f deploy/compose.yaml run --rm --entrypoint zepp-login zepp
```

Re-run step 4 before the token expires (about 30 days); `zepp_auth_status` shows the expiry.

## Checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/mcp                                   # 401
curl -s -o /dev/null -w '%{http_code}\n' -H 'Authorization: Bearer wrong' http://localhost:8080/mcp   # 401
curl -s http://localhost:8080/healthz                                                                 # ok
```
