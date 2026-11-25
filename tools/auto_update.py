#!/usr/bin/env python3
"""Unattended run for the scheduler, logged to .cache/auto-update.log.

With a git remote, the GitHub Action is the only updater: this script just pulls and re-installs,
so local and remote histories never diverge. Without a remote it updates and commits locally.
"""
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
        has_remote = (skillsync.ROOT / ".git").exists() and skillsync.git("remote", cwd=skillsync.ROOT, check=False)
        dirty = has_remote and skillsync.git("status", "--porcelain", "--untracked-files=no", cwd=skillsync.ROOT)
        if dirty:
            # Never stash or merge someone's work in progress from a background job: an autostash
            # that conflicts leaves the repo half-merged and every later run fails.
            print("  skipped pull: uncommitted changes in the repo (commit or discard them)")
            rc = 1
        elif has_remote:
            before = skillsync.git("rev-parse", "HEAD", cwd=skillsync.ROOT)
            print(skillsync.git("pull", "--ff-only", cwd=skillsync.ROOT) or "pulled")
            after = skillsync.git("rev-parse", "HEAD", cwd=skillsync.ROOT)
            print(f"  {before[:8]} -> {after[:8]}" if before != after else "  already up to date")
        else:
            rc |= skillsync.main(["update", "--commit"])
        rc |= skillsync.main(["install"])
        rc |= skillsync.main(["check"])
    except SystemExit as exc:
        rc |= int(exc.code or 0)
    except Exception as exc:  # keep the scheduler quiet, but record why
        print(f"crash: {exc!r}")
        rc = 1
    print(f"exit {rc}")

old = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
log_path.write_text((old + buf.getvalue())[-200_000:], encoding="utf-8")
sys.exit(rc)
