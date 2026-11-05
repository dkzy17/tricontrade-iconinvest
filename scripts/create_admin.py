"""
Deprecated legacy administrator bootstrap.

This script used an obsolete database implementation and contained
hardcoded credentials. It is intentionally disabled.

Use scripts/create_admins.py with the deployment-specific environment
settings instead.
"""

if __name__ == "__main__":
    raise SystemExit(
        "This legacy script is disabled. "
        "Use scripts/create_admins.py with configured environment settings."
    )
