"""
Claude Code Stop hook — saves session transcript to docs/sessions/.
Configure in .claude/settings.json:
  { "hooks": { "Stop": [{ "command": "python3 scripts/extract_session.py" }] } }
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent.parent / "docs" / "sessions"


def main():
    # Claude Code passes session data via stdin as JSON
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        data = {}

    session_id = data.get("session_id", "unknown")
    filename = f"{timestamp}-{session_id[:8]}.json"

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SESSIONS_DIR / filename

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Session saved: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
