"""Upload every file under v3/outputs into the configured Supabase table."""

from __future__ import annotations

import sys
from pathlib import Path


V3_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3_ROOT))

import config  # noqa: E402
from utils.supabase_outputs import iter_output_files, sync_outputs_dir, validate_supabase_config  # noqa: E402


def main() -> int:
    ok, reason = validate_supabase_config()
    if not ok:
        print(f"Supabase sync is not ready: {reason}")
        return 1

    outputs_dir = V3_ROOT / "outputs"
    files = iter_output_files(outputs_dir)
    print(f"Found output files: {len(files)}")

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
