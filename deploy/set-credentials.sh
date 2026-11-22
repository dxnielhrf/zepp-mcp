#!/bin/sh
# Store the Zepp e-mail and password for automatic re-login. Run as root on the
# Docker host, interactively. The password is read without echo and only ever
# written to the file (mode 400, owned by the container user 10001).
set -eu
f="${1:-/etc/zepp-mcp/credentials}"
[ -t 0 ] || { echo "Run this in an interactive terminal." >&2; exit 1; }
install -d -m 700 "$(dirname "$f")"
printf 'Zepp e-mail: '
IFS= read -r email
trap 'stty echo' EXIT INT TERM
stty -echo
printf 'Zepp password (hidden): '
IFS= read -r pw
stty echo
echo
if [ -z "$email" ] || [ -z "$pw" ]; then
  echo "E-mail and password are required. Nothing written." >&2
  exit 1
fi
umask 077
printf '%s\n%s\n' "$email" "$pw" > "$f"
pw=
chown 10001:10001 "$f"
chmod 400 "$f"
echo "Saved to $f. Apply with: docker compose -f deploy/compose.yaml up -d"
