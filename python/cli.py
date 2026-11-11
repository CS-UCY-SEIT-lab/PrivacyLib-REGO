"""Optional command-line caller for the Python GDPR router."""
import json
from pathlib import Path
import sys

from gdpr_router import GdprRouter


def main() -> int:
    if not 2 <= len(sys.argv) <= 4:
        raise ValueError("Usage: python python/cli.py <policy> [input.json] [user_id]")
    policy = sys.argv[1]
    file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "gdpr/input.json"
    user_id = sys.argv[3] if len(sys.argv) > 3 else None
    with file.open(encoding="utf-8-sig") as handle:
        input_data = json.load(handle)
    print(json.dumps(GdprRouter().route(policy, input_data, user_id), indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
