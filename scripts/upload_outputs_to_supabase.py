"""Upload every file under v3/outputs into the configured Supabase table."""

from __future__ import annotations

import sys
from pathlib import Path


V3_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3_ROOT))

import config  # noqa: E402
from utils.supabase_outputs import sync_outputs_dir  # noqa: E402


def main() -> int:
    if not config.SUPABASE_URL or not (
        config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_ANON_KEY
    ):
        print("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")
        return 1

    outputs_dir = V3_ROOT / "outputs"
    uploaded, failed = sync_outputs_dir(outputs_dir)

    print(f"Uploaded files: {uploaded}")
    if failed:
        print("Failed files:")
        for path in failed:
            print(f"  - {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
