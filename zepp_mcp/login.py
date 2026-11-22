"""One-time interactive Zepp login (fork).

Asks for the password with getpass, makes exactly one login attempt and
stores only the resulting token (mode 600) in the token cache. The password
is never written anywhere. Run it again when the token is about to expire.
"""

from __future__ import annotations

import getpass
import os
import sys

import httpx

from . import auth


def main() -> int:
    if not auth.cache_enabled():
        print("ZEPP_TOKEN_CACHE is off, so a token could not be stored.", file=sys.stderr)
        return 2
    current = auth.load_cached()
    if current:
        answer = input(f"A valid token exists ({auth.describe_expiry(current)}). "
                       "Log in again anyway? [y/N] ").strip().lower()
        if answer not in ("y", "yes", "j", "ja"):
            print("Nothing changed.")
            return 0
    email = os.environ.get("ZEPP_EMAIL") or input("Zepp e-mail: ").strip()
    password = getpass.getpass("Zepp password (not stored): ")
    if not email or not password:
        print("E-mail and password are required. No login attempt made.", file=sys.stderr)
        return 2
    country = os.environ.get("ZEPP_COUNTRY", "US")
    try:
        with httpx.Client(timeout=30) as http:
            credential = auth.login(http, email, password, country)  # one attempt
    except auth.LoginError as exc:
        print(f"Login failed, not retried: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"Network error during login, not retried: {type(exc).__name__}",
              file=sys.stderr)
        return 1
    finally:
        del password
    auth.save_cached(credential)
    if auth.load_cached() is None:
        print(f"Login worked, but the token could not be written to {auth.cache_path()}.",
              file=sys.stderr)
        return 1
    print(f"OK. Token stored in {auth.cache_path()} ({auth.describe_expiry(credential)}), "
          f"region {credential.region_host}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
