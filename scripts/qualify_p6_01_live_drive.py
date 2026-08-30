#!/usr/bin/env python3
"""Optional live P6-01 Drive lifecycle proof. Never invoked by pytest/CI.

Usage:
  uv run --extra dev python scripts/qualify_p6_01_live_drive.py --execute

Proves bind → map → validate → save-version → approve → ready → revise against
a real customer Drive connection. Does not fabricate success.
"""

from __future__ import annotations

import argparse
import os
import sys


def _blocker(reason: str) -> int:
    print("P6_01_LIVE_E2E_BLOCKED")
    print(reason)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        return _blocker("Operator did not pass --execute.")

    missing: list[str] = []
    if not (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip():
        missing.append("GOOGLE_OAUTH_CLIENT_ID is unset")
    if not (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip():
        missing.append("GOOGLE_OAUTH_CLIENT_SECRET is unset")
    if not (os.getenv("GOOGLE_KMS_KEY") or "").strip():
        missing.append("GOOGLE_KMS_KEY is unset (required for live Google credential vault)")
    if not (os.getenv("CLERK_SECRET_KEY") or "").strip():
        missing.append("CLERK_SECRET_KEY is unset (P6-01 HTTP tenant/project authority is Clerk-bound)")
    if missing:
        return _blocker(
            "Live P6-01 Drive lifecycle cannot run: "
            + "; ".join(missing)
            + ". The API uses RestDriveClient only after Google OAuth client id/secret "
            "and GOOGLE_KMS_KEY are configured, and bind/approve require an authenticated "
            "tenant with a live DriveWorkspaceBinding access token. No authorized customer "
            "Drive connection is available in this environment."
        )
    return _blocker(
        "Google OAuth client credentials are present, but this operator script does not "
        "mint a customer Drive access token or Clerk session. Live bind→revise still "
        "requires an existing authorized GoogleConnection + Drive budget folder binding."
    )


if __name__ == "__main__":
    sys.exit(main())
