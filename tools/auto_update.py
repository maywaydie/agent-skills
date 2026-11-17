#!/usr/bin/env python3
"""Unattended run for the scheduler: update -> commit -> install, logged to .cache/auto-update.log."""
import contextlib
import datetime as dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skillsync  # noqa: E402

log_path = skillsync.ROOT / ".cache" / "auto-update.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
buf = io.StringIO()
rc = 0
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    print(f"=== {dt.datetime.now().isoformat(timespec='seconds')}")
    try:
        rc |= skillsync.main(["update", "--commit"])
        rc |= skillsync.main(["install"])
    except SystemExit as exc:
        rc |= int(exc.code or 0)
    except Exception as exc:  # keep the scheduler quiet, but record why
        print(f"crash: {exc!r}")
        rc = 1
    print(f"exit {rc}")

old = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
log_path.write_text((old + buf.getvalue())[-200_000:], encoding="utf-8")
sys.exit(rc)
