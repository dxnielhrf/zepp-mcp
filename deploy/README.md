# Deploy: Streamable HTTP behind a bearer token

`zepp-mcp` speaks stdio. This stack wraps it with `mcp-proxy` (Streamable HTTP at `/mcp`) and puts Caddy in front: `/healthz` is open, everything else needs `Authorization: Bearer <token>`, otherwise 401. The server container publishes no port and runs as a non-root user on a read-only root filesystem with all capabilities dropped. The Zepp password is stored only if you choose automatic re-login (step 3); the token cache lives in the `zepp-token` volume (file mode 600).

## Setup

```bash
# 1. Bearer token, root-only, outside the repository
install -d -m 700 /etc/zepp-mcp
umask 077; printf 'MCP_BEARER_TOKEN=%s\n' "$(openssl rand -hex 32)" > /etc/zepp-mcp/bearer.env

# 2. Optional: run the test suite on Linux
docker build -f deploy/Dockerfile --target test .

# 3. Zepp credentials for automatic re-login (the phone app invalidates the
#    server's token whenever it opens). Or `touch` an empty file for token-only mode.
sh deploy/set-credentials.sh            # writes /etc/zepp-mcp/credentials (400, uid 10001)

# 4. Build and start (BEARER_ENV_FILE defaults to /etc/zepp-mcp/bearer.env)
docker compose -f deploy/compose.yaml up -d --build

# 5. Optional: one interactive Zepp login (password via getpass, one attempt, only the token is kept)
docker compose -f deploy/compose.yaml run --rm --entrypoint zepp-login zepp
```

With stored credentials the server logs in once by itself when Zepp rejects the token. One rejected login blocks further automatic logins until step 5 succeeds; `zepp_auth_status` shows `auto_login`. Token-only mode: re-run step 5 before the token expires (about 30 days).

## Checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/mcp                                   # 401
curl -s -o /dev/null -w '%{http_code}\n' -H 'Authorization: Bearer wrong' http://localhost:8080/mcp   # 401
curl -s http://localhost:8080/healthz                                                                 # ok
```
