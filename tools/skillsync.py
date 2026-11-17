#!/usr/bin/env python3
"""skillsync - keep a curated, conflict-free set of agent skills up to date.

The manifest (skills.toml) says which skills to take from which GitHub repos.
`update` fetches the tracked branch of every source, copies the chosen skill
folders into skills/, and records the exact commit in skills.lock.json.
`check` validates the whole set (names, frontmatter, licences, overlaps).
`install` links every skill into the agent skill folders (Claude Code, Codex,
OpenCode, Cursor ...) without touching anything it does not own.

Only the Python 3.11+ standard library and git are needed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "skills.toml"
LOCK = ROOT / "skills.lock.json"
SKILLS = ROOT / "skills"
CACHE = ROOT / ".cache" / "sources"
CHANGELOG = ROOT / "CHANGELOG.md"
PLUGIN_DIR = ROOT / ".claude-plugin"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LICENSE_RE = re.compile(r"^(licen[cs]e|copying|notice)([-._][a-z0-9.-]+)?$", re.I)
# Files that only describe things. Anything else counts as code for the review gate.
DOC_EXT = {".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf"}
ALWAYS_EXCLUDE = [".git", ".git/*", ".github/*", "__pycache__/*", "*.pyc", "node_modules/*", ".DS_Store"]
STOPWORDS = set(
    "a an and are as at be by for from has have in into is it its of on or that the this to use used "
    "using when with whenever any all you your user users skill skills should can will before after "
    "also not do does such e g eg etc like".split()
)

if os.name == "nt":  # keep unicode output readable on Windows consoles
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


# ----------------------------------------------------------------- helpers

def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-c", "advice.detachedHead=false", *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def load_manifest() -> dict:
    if not MANIFEST.exists():
        die(f"{MANIFEST} not found")
    with MANIFEST.open("rb") as fh:
        data = tomllib.load(fh)
    data.setdefault("settings", {})
    data.setdefault("sources", {})
    data.setdefault("skill", [])
    for s in data["skill"]:
        s.setdefault("as", s.get("name"))
        if not s.get("as"):
            die(f"skill entry without name: {s}")
        if s.get("local"):
            continue
        if s.get("source") not in data["sources"]:
            die(f"skill {s['as']}: unknown source {s.get('source')!r}")
        s.setdefault("path", f"skills/{s['name']}")
    return data


def load_lock() -> dict:
    if LOCK.exists():
        return json.loads(LOCK.read_text(encoding="utf-8"))
    return {"sources": {}, "skills": {}}


def save_lock(lock: dict) -> None:
    lock["sources"] = dict(sorted(lock["sources"].items()))
    lock["skills"] = dict(sorted(lock["skills"].items()))
    LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def repo_url(src: dict) -> str:
    repo = src["repo"]
    return repo if "://" in repo else f"https://github.com/{repo}"


def web_url(src: dict) -> str:
    return repo_url(src).removesuffix(".git")


def iter_files(base: Path):
    # Sort by the posix string, not by Path: Windows paths compare case-insensitively,
    # which would give a different order (and hash) than on Linux CI.
    files = [(p.relative_to(base).as_posix(), p) for p in base.rglob("*") if p.is_file()]
    yield from sorted(files, key=lambda item: item[0])


def tree_hash(base: Path) -> str:
    h = hashlib.sha256()
    for rel, p in iter_files(base):
        if rel == "SOURCE.md":
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:16]


def file_digests(base: Path) -> dict[str, str]:
    if not base.exists():
        return {}
    return {rel: hashlib.sha256(p.read_bytes()).hexdigest() for rel, p in iter_files(base) if rel != "SOURCE.md"}


def is_code(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if LICENSE_RE.match(name):
        return False
    return Path(name).suffix.lower() not in DOC_EXT


def parse_frontmatter(text: str) -> dict:
    """Small YAML subset: top-level `key: value`, quoted strings, | and > blocks."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    lines = text[3:end].strip("\n").splitlines()
    out: dict[str, str] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+", ""):
            block = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            # `|` keeps newlines; `>` and a plain multi-line scalar fold them into spaces
            val = ("\n" if val.startswith("|") else " ").join(b for b in block if b)
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def set_frontmatter_name(skill_md: Path, new_name: str) -> None:
    text = skill_md.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    head, rest = text[:end], text[end:]
    head, n = re.subn(r"(?m)^name:\s*.*$", f"name: {new_name}", head, count=1)
    if not n:
        head = head.replace("---", f"---\nname: {new_name}", 1)
    skill_md.write_text(head + rest, encoding="utf-8")


# ----------------------------------------------------------------- fetching

def fetch_source(key: str, src: dict, paths: list[str]) -> tuple[Path, str, str]:
    """Shallow, sparse checkout of the tracked branch. Returns (dir, sha, commit date)."""
    ref = src.get("ref", "main")
    dest = CACHE / key
    want = sorted(set(paths) | {"/LICENSE*", "/LICENCE*", "/COPYING*", "/NOTICE*"})
    if not (dest / ".git").exists():
        if dest.exists():
            shutil.rmtree(dest, onerror=_force_remove)
        dest.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "--branch", ref,
            repo_url(src), str(dest))
    else:
        git("remote", "set-url", "origin", repo_url(src), cwd=dest)
        git("fetch", "--depth", "1", "origin", ref, cwd=dest)
    git("sparse-checkout", "init", "--no-cone", cwd=dest)
    git("sparse-checkout", "set", "--no-cone", *[p if p.startswith("/") else f"/{p}/" for p in want], cwd=dest)
    target = "FETCH_HEAD" if (dest / ".git" / "FETCH_HEAD").exists() else "HEAD"
    git("checkout", "--force", "--detach", target, cwd=dest)
    sha = git("rev-parse", "HEAD", cwd=dest)
    date = git("log", "-1", "--format=%cI", cwd=dest)
    return dest, sha, date


def remote_head(src: dict) -> str | None:
    try:
        out = git("ls-remote", repo_url(src), f"refs/heads/{src.get('ref', 'main')}")
    except RuntimeError:
        return None
    return out.split()[0] if out else None


def _force_remove(func, path, _exc):
    os.chmod(path, 0o700)
    func(path)


def copy_skill(src_dir: Path, dest: Path, exclude: list[str], repo_root: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest, onerror=_force_remove)
    patterns = ALWAYS_EXCLUDE + exclude
    for rel, p in iter_files(src_dir):
        if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    if not any(LICENSE_RE.match(p.name) and not p.name.lower().startswith("notice") for p in dest.iterdir()):
        for lic in sorted(repo_root.iterdir()):  # all of them: dual licences, NOTICE files
            if lic.is_file() and LICENSE_RE.match(lic.name):
                shutil.copy2(lic, dest / lic.name)


def write_source_md(dest: Path, skill: dict, src: dict, sha: str, date: str) -> None:
    url = f"{web_url(src)}/tree/{sha}/{skill['path']}"
    lines = [
        f"# Source of `{skill['as']}`",
        "",
        f"- Upstream: {web_url(src)} (`{skill['path']}`, branch `{src.get('ref', 'main')}`)",
        f"- Commit: [{sha[:12]}]({url}) from {date}",
        f"- Licence: {src.get('license', 'see LICENSE in this folder')}",
        f"- Vendored by tools/skillsync.py on {dt.date.today().isoformat()}. Do not edit by hand:",
        "  the next update overwrites this folder. Put local changes in a skill of your own.",
    ]
    if skill["as"] != skill["name"]:
        lines.append(f"- Renamed from `{skill['name']}` to `{skill['as']}` to avoid a name clash.")
    (dest / "SOURCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------- commands

def cmd_update(args) -> int:
    man, lock = load_manifest(), load_lock()
    wanted = set(args.skills or [])
    skills = [s for s in man["skill"] if not s.get("local") and (not wanted or s["as"] in wanted)]
    if wanted - {s["as"] for s in skills}:
        die(f"not in manifest: {', '.join(sorted(wanted - {s['as'] for s in skills}))}")
    by_source: dict[str, list[dict]] = {}
    for s in skills:
        by_source.setdefault(s["source"], []).append(s)

    changes, held, failed = [], [], []
    SKILLS.mkdir(exist_ok=True)
    for key, group in sorted(by_source.items()):
        src = man["sources"][key]
        prev_sha = lock["sources"].get(key, {}).get("commit")
        all_present = all((SKILLS / s["as"]).exists() and s["as"] in lock["skills"] for s in group)
        if not args.force and prev_sha and all_present:
            head = remote_head(src)
            if head == prev_sha:
                print(f"  = {key}: up to date ({prev_sha[:8]})")
                continue
        print(f"  ~ {key}: fetching {repo_url(src)} [{src.get('ref', 'main')}]")
        try:
            repo_dir, sha, date = fetch_source(key, src, [s["path"] for s in group])
        except RuntimeError as exc:
            failed.append(f"{key}: {exc}")
            print(f"  ! {key}: {exc}")
            continue
        trust = src.get("trust", man["settings"].get("default_trust", "review"))
        source_ok = False
        for s in group:
            name, src_dir = s["as"], repo_dir / s["path"]
            if not (src_dir / "SKILL.md").exists():
                failed.append(f"{name}: {s['path']}/SKILL.md missing upstream at {sha[:8]} (kept old copy)")
                print(f"  ! {name}: SKILL.md missing upstream, kept old copy")
                continue
            dest = SKILLS / name
            staging = ROOT / ".cache" / "staging" / name
            copy_skill(src_dir, staging, s.get("exclude", []), repo_dir)
            if name != s["name"]:
                set_frontmatter_name(staging / "SKILL.md", name)
            old, new = file_digests(dest), file_digests(staging)
            if old == new:
                shutil.rmtree(staging, onerror=_force_remove)
                source_ok = True
                lock["skills"].setdefault(name, {}).update(source=key, path=s["path"], commit=sha, hash=tree_hash(dest))
                continue
            code_changes = sorted(r for r in set(old) ^ set(new) | {r for r in old if r in new and old[r] != new[r]} if is_code(r))
            is_new = not old
            if code_changes and not is_new and trust != "auto" and name not in (args.approve or []) and not args.approve_all:
                held.append((name, key, sha, code_changes))
                shutil.rmtree(staging, onerror=_force_remove)
                print(f"  ? {name}: held for review ({len(code_changes)} code file(s) changed)")
                continue
            if dest.exists():
                shutil.rmtree(dest, onerror=_force_remove)
            shutil.move(str(staging), str(dest))
            write_source_md(dest, s, src, sha, date)
            prev = lock["skills"].get(name, {}).get("commit")
            lock["skills"][name] = {"source": key, "path": s["path"], "commit": sha, "hash": tree_hash(dest)}
            source_ok = True
            changes.append((name, key, prev, sha, sorted(set(old) ^ set(new) | {r for r in old if r in new and old[r] != new[r]})))
            print(f"  + {name}: {'added' if is_new else 'updated'} -> {sha[:8]}")
        if source_ok:
            lock["sources"][key] = {"repo": src["repo"], "ref": src.get("ref", "main"), "commit": sha, "date": date}

    # drop vendored skills that left the manifest
    keep = {s["as"] for s in man["skill"]}
    if not wanted:
        for name in sorted(set(lock["skills"]) - keep):
            if (SKILLS / name).exists() and (SKILLS / name / "SOURCE.md").exists():
                shutil.rmtree(SKILLS / name, onerror=_force_remove)
            lock["skills"].pop(name, None)
            changes.append((name, "-", None, None, ["removed from manifest"]))
            print(f"  - {name}: removed (no longer in manifest)")
        for key in set(lock["sources"]) - set(man["sources"]):
            lock["sources"].pop(key)

    lock["held"] = {n: {"source": k, "commit": c, "code_files": f} for n, k, c, f in held}
    lock["checked"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    save_lock(lock)
    write_changelog(man, changes, held, failed)
    write_plugin_files(man)
    print(f"\n{len(changes)} change(s), {len(held)} held for review, {len(failed)} problem(s)")
    for f in failed:
        print(f"  ! {f}")
    if held:
        print("  review with:  python tools/skillsync.py diff <name>   then:  update --approve <name>")
    rc = cmd_check(argparse.Namespace(quiet=True))
    if args.commit and (changes or held):
        git_commit(changes)
    return 1 if failed or rc else 0


def write_changelog(man, changes, held, failed) -> None:
    if not (changes or held or failed):
        return
    out = [f"## {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for name, key, prev, sha, files in changes:
        if sha is None:
            out.append(f"- **{name}**: removed")
            continue
        base = web_url(man["sources"][key])
        link = f"[{prev[:8]}...{sha[:8]}]({base}/compare/{prev}...{sha})" if prev and prev != sha else f"`{sha[:8]}`"
        out.append(f"- **{name}** ({key}): {'updated' if prev else 'added'} {link}, {len(files)} file(s)")
    for name, key, sha, files in held:
        out.append(f"- **{name}** ({key}): HELD at old version, upstream `{sha[:8]}` changes code: {', '.join(files[:6])}")
    for f in failed:
        out.append(f"- problem: {f}")
    old = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Changelog\n\nWritten by `tools/skillsync.py update`.\n"
    head, _, tail = old.partition("\n## ")
    CHANGELOG.write_text(head.rstrip() + "\n\n" + "\n".join(out) + "\n" + (("\n## " + tail) if tail else ""), encoding="utf-8")


def git_commit(changes) -> None:
    if not (ROOT / ".git").exists():
        print("  (not a git repo, skipping commit)")
        return
    paths = ["skills", "skills.lock.json", "CHANGELOG.md", ".claude-plugin"]
    git("add", "-A", "--", *paths, cwd=ROOT)
    if not git("diff", "--cached", "--name-only", "--", *paths, cwd=ROOT):
        return
    names = ", ".join(sorted({c[0] for c in changes})) or "lock refresh"
    msg = f"skills: update {names}"[:200]
    git("commit", "-m", msg, "--", *paths, cwd=ROOT)
    print(f"  committed: {msg}")


def write_plugin_files(man) -> None:
    """Make the repo installable as a Claude Code plugin marketplace."""
    meta = man["settings"].get("plugin", {})
    name = meta.get("name", "agent-skills")
    owner = meta.get("owner", "agent-skills")
    skills = [f"./{s['as']}" for s in man["skill"] if (SKILLS / s["as"] / "SKILL.md").exists()]
    PLUGIN_DIR.mkdir(exist_ok=True)
    plugin = {
        "name": name,
        "description": meta.get("description", "Curated, auto-updated agent skills"),
        "version": dt.date.today().strftime("%Y.%m.%d"),
        "author": {"name": owner},
    }
    if meta.get("repository"):
        plugin["repository"] = meta["repository"]
    market = {
        "name": name,
        "owner": {"name": owner},
        "metadata": {"description": plugin["description"]},
        "plugins": [{**plugin, "source": "./skills", "strict": False, "skills": skills}],
    }
    for fname, obj in (("plugin.json", plugin), ("marketplace.json", market)):
        (PLUGIN_DIR / fname).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_readme_table(man)


def write_readme_table(man) -> None:
    """Regenerate the skill table between the markers in README.md."""
    readme = ROOT / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- skills:start -->", "<!-- skills:end -->"
    if start not in text or end not in text:
        return
    lock = load_lock()
    rows = ["| Skill | Domain | Source | Commit |", "| --- | --- | --- | --- |"]
    for s in sorted(man["skill"], key=lambda x: (x.get("domain", ""), x["as"])):
        if s.get("local"):
            rows.append(f"| `{s['as']}` | {s.get('domain', '')} | local | - |")
            continue
        src = man["sources"][s["source"]]
        commit = lock["skills"].get(s["as"], {}).get("commit", "")
        link = f"[{commit[:8]}]({web_url(src)}/tree/{commit}/{s['path']})" if commit else "-"
        rows.append(f"| `{s['as']}` | {s.get('domain', '')} | [{src['repo']}]({web_url(src)}) | {link} |")
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    readme.write_text(f"{head}{start}\n" + "\n".join(rows) + f"\n{end}{tail}", encoding="utf-8")


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9+#.-]{2,}", text.lower()) if w not in STOPWORDS}


def unmanaged_names(targets: list[Path]) -> dict[str, Path]:
    found = {}
    for t in targets:
        if not t.exists():
            continue
        for d in t.iterdir():
            if d.is_dir() and not owned_link(d) and (d / "SKILL.md").exists():
                fm = parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
                found.setdefault(fm.get("name", d.name), d)
    return found


def cmd_check(args) -> int:
    man, lock = load_manifest(), load_lock()
    errors, warns = [], []
    seen_name, seen_domain, descs = {}, {}, {}
    for s in man["skill"]:
        name = s["as"]
        d = SKILLS / name
        md = d / "SKILL.md"
        if not md.exists():
            errors.append(f"{name}: skills/{name}/SKILL.md missing (run update)")
            continue
        fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        fname, desc = fm.get("name", ""), fm.get("description", "")
        if fname != name:
            errors.append(f"{name}: frontmatter name is {fname!r}, folder is {name!r} (set `as` in manifest)")
        if not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{name}: name must be lowercase-hyphenated, <= 64 chars")
        if not desc:
            errors.append(f"{name}: no description, the agent can never pick it")
        elif len(desc) > 1024:
            warns.append(f"{name}: description is {len(desc)} chars (> 1024, some agents truncate)")
        if name in seen_name:
            errors.append(f"{name}: duplicate name (also {seen_name[name]})")
        seen_name[name] = s.get("source", "local")
        dom = s.get("domain")
        if not dom:
            warns.append(f"{name}: no domain set in manifest")
        elif dom in seen_domain:
            errors.append(f"{name}: domain '{dom}' already covered by {seen_domain[dom]} - keep one skill per job")
        else:
            seen_domain[dom] = name
        if not s.get("local"):
            if not any(LICENSE_RE.match(p.name) for p in d.iterdir()):
                errors.append(f"{name}: no licence file vendored")
            locked = lock["skills"].get(name)
            if not locked:
                errors.append(f"{name}: not in skills.lock.json")
            elif tree_hash(d) != locked["hash"]:
                errors.append(f"{name}: edited by hand since last update (hash mismatch); move edits to a local skill")
        descs[name] = tokens(desc)
    names = sorted(descs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not descs[a] or not descs[b]:
                continue
            j = len(descs[a] & descs[b]) / len(descs[a] | descs[b])
            if j >= man["settings"].get("overlap_threshold", 0.3):
                warns.append(f"{a} / {b}: descriptions overlap ({j:.0%}), they may compete for the same requests")
    targets = install_targets(man)
    for other, where in unmanaged_names(targets).items():
        if other in seen_name:
            errors.append(f"{other}: a different skill with this name is already installed at {where}")
    for name, info in lock.get("held", {}).items():
        warns.append(f"{name}: upstream update held for review ({len(info['code_files'])} code file(s))")
    for w in warns:
        print(f"  warn  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    if not getattr(args, "quiet", False) or errors:
        print(f"check: {len(seen_name)} skill(s), {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


def cmd_diff(args) -> int:
    man, lock = load_manifest(), load_lock()
    s = next((x for x in man["skill"] if x["as"] == args.skill), None)
    if not s or s.get("local"):
        die(f"{args.skill} is not a vendored skill")
    src = man["sources"][s["source"]]
    repo_dir, sha, _ = fetch_source(s["source"], src, [s["path"]])
    old = lock["skills"].get(s["as"], {}).get("commit")
    print(f"{s['as']}: {old[:8] if old else 'none'} -> {sha[:8]}  {web_url(src)}/compare/{old}...{sha}\n")
    proc = subprocess.run(["git", "diff", "--no-index", "--stat", str(SKILLS / s["as"]), str(repo_dir / s["path"])],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout or "(no differences)")
    if args.full:
        proc = subprocess.run(["git", "diff", "--no-index", str(SKILLS / s["as"]), str(repo_dir / s["path"])],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(proc.stdout)
    return 0


def cmd_status(args) -> int:
    man, lock = load_manifest(), load_lock()
    heads = {}
    if args.remote:
        for key, src in man["sources"].items():
            heads[key] = remote_head(src)
    print(f"{'skill':34} {'domain':22} {'source':16} {'commit':9} state")
    for s in man["skill"]:
        name, key = s["as"], s.get("source", "local")
        locked = lock["skills"].get(name, {})
        commit = locked.get("commit", "")[:8] if not s.get("local") else "-"
        state = "local" if s.get("local") else ("missing" if not (SKILLS / name).exists() else "ok")
        if name in lock.get("held", {}):
            state = "held"
        elif args.remote and not s.get("local") and heads.get(key) and heads[key] != locked.get("commit"):
            state = "behind"
        print(f"{name:34} {s.get('domain', ''):22} {key:16} {commit:9} {state}")
    print(f"\nlast update check: {lock.get('checked', 'never')}")
    return 0


# ----------------------------------------------------------------- install

def install_targets(man) -> list[Path]:
    raw = man["settings"].get("targets", ["~/.claude/skills", "~/.agents/skills"])
    return [Path(os.path.expandvars(os.path.expanduser(t))) for t in raw]


def link_target(p: Path) -> Path | None:
    try:
        if p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p)):
            return Path(os.path.realpath(p))
    except OSError:
        return None
    return None


def owned_link(p: Path) -> bool:
    t = link_target(p)
    if t is None:
        return (p / ".skillsync").exists()  # copy-mode install
    try:
        t.relative_to(SKILLS.resolve())
        return True
    except ValueError:
        return False


def remove_owned(p: Path) -> None:
    if link_target(p) is not None:
        if os.name == "nt":
            os.rmdir(p)  # removes the junction only, never the target
        else:
            p.unlink()
    else:
        shutil.rmtree(p, onerror=_force_remove)


def make_link(link: Path, target: Path, mode: str) -> None:
    if mode == "copy":
        shutil.copytree(target, link)
        (link / ".skillsync").write_text(str(target), encoding="utf-8")
    elif os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def cmd_install(args) -> int:
    man = load_manifest()
    mode = args.mode or man["settings"].get("install_mode", "link")
    names = {s["as"] for s in man["skill"] if (SKILLS / s["as"] / "SKILL.md").exists()}
    conflicts = 0
    for target in install_targets(man):
        target.mkdir(parents=True, exist_ok=True)
        added = removed = 0
        for entry in list(target.iterdir()):
            if owned_link(entry) and (entry.name not in names or (mode == "copy") != (link_target(entry) is None)):
                remove_owned(entry)
                removed += 1
        for name in sorted(names):
            link = target / name
            if link.exists() or link.is_symlink():
                if owned_link(link):
                    if mode == "copy":
                        remove_owned(link)
                    else:
                        continue
                else:
                    print(f"  conflict: {link} exists and is not managed here - left alone, {name} not installed")
                    conflicts += 1
                    continue
            make_link(link, SKILLS / name, mode)
            added += 1
        print(f"  {target}: +{added} -{removed} ({len(names)} managed)")
    return 1 if conflicts else 0


def cmd_uninstall(args) -> int:
    man = load_manifest()
    for target in install_targets(man):
        if not target.exists():
            continue
        n = 0
        for entry in list(target.iterdir()):
            if owned_link(entry):
                remove_owned(entry)
                n += 1
        print(f"  {target}: removed {n}")
    return 0


# ----------------------------------------------------------------- schedule

def cmd_schedule(args) -> int:
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    exe = pyw if pyw.exists() else py
    script = ROOT / "tools" / "auto_update.py"
    name = "agent-skills-update"
    if os.name != "nt":
        print(f"Add to crontab:  0 */12 * * * {py} {script}")
        return 0
    if args.remove:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", name])
        return 0
    cmd = f'"{exe}" "{script}"'
    proc = subprocess.run(["schtasks", "/Create", "/F", "/TN", name, "/SC", "HOURLY", "/MO", str(args.every_hours),
                           "/TR", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout or proc.stderr)
    return proc.returncode


# ----------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("update", help="fetch upstream and refresh vendored skills")
    p.add_argument("skills", nargs="*", help="only these skills (default: all)")
    p.add_argument("--force", action="store_true", help="re-copy even if upstream did not move")
    p.add_argument("--approve", nargs="*", metavar="NAME", help="accept held code changes for these skills")
    p.add_argument("--approve-all", action="store_true", help="accept every held code change")
    p.add_argument("--commit", action="store_true", help="git-commit the result")
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser("check", help="validate names, licences, domains and overlaps")
    p.set_defaults(fn=cmd_check, quiet=False)
    p = sub.add_parser("status", help="list skills and their pinned commits")
    p.add_argument("--remote", action="store_true", help="also ask upstream whether a newer commit exists")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("diff", help="show what an update of one skill would change")
    p.add_argument("skill")
    p.add_argument("--full", action="store_true")
    p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("install", help="link skills into agent skill folders")
    p.add_argument("--mode", choices=["link", "copy"])
    p.set_defaults(fn=cmd_install)
    p = sub.add_parser("uninstall", help="remove only the links this tool created")
    p.set_defaults(fn=cmd_uninstall)
    p = sub.add_parser("schedule", help="register a periodic auto-update (Windows Task Scheduler)")
    p.add_argument("--every-hours", type=int, default=12)
    p.add_argument("--remove", action="store_true")
    p.set_defaults(fn=cmd_schedule)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
