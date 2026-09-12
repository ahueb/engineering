"""Safe, atomic file writes plus structured backup/restore for the installer.

Python >= 3.8, stdlib only. See docs/plans/2026-09-12-installer-merge-hardening.md
(decisions 4-5) and the shared interface contract for the exact behaviour.

Subcommands: write, backup, restore, list, check, mode.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile

STAMP_RE = re.compile(r"^\d{8}T\d{6}Z-\d+$")
SCHEMA = 1


class SafeWriteError(Exception):
    """Carries the exit code that main() should use."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------
# Low-level checks and atomic write
# --------------------------------------------------------------------------


def check_target(target, break_hardlinks=False):
    """Refuse a directory/FIFO/socket target, or a hard-linked one without the flag.

    A missing target (nothing at the resolved real path) is fine and returns
    silently. Raises SafeWriteError(4, ...) or SafeWriteError(5, ...).
    """
    real = os.path.realpath(target)
    if not os.path.exists(real):
        return
    st = os.stat(real)
    mode = st.st_mode
    if stat.S_ISDIR(mode):
        raise SafeWriteError(4, "refused: {} resolves to a directory".format(target))
    if stat.S_ISFIFO(mode):
        raise SafeWriteError(4, "refused: {} resolves to a FIFO".format(target))
    if hasattr(stat, "S_ISSOCK") and stat.S_ISSOCK(mode):
        raise SafeWriteError(4, "refused: {} resolves to a socket".format(target))
    if st.st_nlink > 1 and not break_hardlinks:
        raise SafeWriteError(
            5,
            "refused: {} is hard-linked (nlink={}); os.replace would silently "
            "detach the other names; use --break-hardlinks to proceed".format(
                target, st.st_nlink
            ),
        )


def _write_atomic(real_dir, real_target, content, mode):
    tmp = tempfile.NamedTemporaryFile(dir=real_dir, delete=False)
    tmp_name = tmp.name
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, real_target)
        try:
            dirfd = os.open(real_dir, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _create_parents(real_dir, cfg=None):
    """Create `real_dir` (0755), creating a missing `cfg` root as 0700 first."""
    if cfg:
        cfg_real = os.path.realpath(cfg)
        if not os.path.isdir(cfg_real):
            os.makedirs(cfg_real, mode=0o700)
            os.chmod(cfg_real, 0o700)
    if not os.path.isdir(real_dir):
        os.makedirs(real_dir, mode=0o755)
        os.chmod(real_dir, 0o755)


def write_target(
    target,
    content,
    default_mode,
    break_hardlinks=False,
    create_through_dangling=False,
    cfg=None,
):
    """Write `content` (bytes) to `target`, atomically, through symlinks.

    Returns "written" or "unchanged". Raises SafeWriteError with the exit
    code documented in the contract. When `cfg` is given and that directory
    is missing, it is created as 0700 before any deeper parent (0755).
    """
    if os.path.islink(target) and not os.path.exists(target):
        if not create_through_dangling:
            raise SafeWriteError(
                4,
                "refused: {} is a dangling symlink; use "
                "--create-through-dangling to create through it".format(target),
            )

    check_target(target, break_hardlinks)

    real_target = os.path.realpath(target)
    real_dir = os.path.dirname(real_target)

    existing = None
    if os.path.exists(real_target):
        with open(real_target, "rb") as f:
            existing = f.read()
        mode = stat.S_IMODE(os.stat(real_target).st_mode)
    else:
        mode = default_mode

    if existing is not None and existing == content:
        return "unchanged"

    if real_dir and not os.path.isdir(real_dir):
        _create_parents(real_dir, cfg)

    try:
        _write_atomic(real_dir, real_target, content, mode)
    except PermissionError as e:
        if os.name == "nt":
            raise SafeWriteError(7, "close Claude Code and rerun")
        raise SafeWriteError(6, "write failed for {}: {}".format(target, e))
    except Exception as e:
        raise SafeWriteError(6, "write failed for {}: {}".format(target, e))

    return "written"


# --------------------------------------------------------------------------
# Backup / restore / list
# --------------------------------------------------------------------------


def _ensure_dir(path, mode):
    """Create `path` if missing, chmod only the directory we just created."""
    if not os.path.isdir(path):
        os.makedirs(path)
        os.chmod(path, mode)
    return path


def _ensure_dir_mode(path, mode):
    """Create `path` if missing and force its mode either way."""
    if not os.path.isdir(path):
        os.makedirs(path)
    os.chmod(path, mode)
    return path


def _stamp_key(name):
    """Sort key for a stamp dir: (timestamp, numeric pid), not lexicographic."""
    ts, _, pid = name.rpartition("-")
    try:
        return (ts, int(pid))
    except ValueError:
        return (ts, 0)


def _list_stamps(engineering_dir):
    if not os.path.isdir(engineering_dir):
        return []
    names = [
        n
        for n in os.listdir(engineering_dir)
        if STAMP_RE.match(n) and os.path.isdir(os.path.join(engineering_dir, n))
    ]
    names.sort(key=_stamp_key)
    return names


def _prune(engineering_dir, keep=5):
    names = _list_stamps(engineering_dir)
    if len(names) <= keep:
        return
    for old in names[: len(names) - keep]:
        shutil.rmtree(os.path.join(engineering_dir, old), ignore_errors=True)


def _existing_files(manifest_path):
    """Return the `files` list of an existing manifest, or [] if unusable."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(manifest, dict):
        return []
    files = manifest.get("files")
    if not isinstance(files, list):
        return []
    return [e for e in files if isinstance(e, dict)]


def _merge_files(old_files, new_files):
    """Merge manifest entries, keyed by `rel`; later entries win, order kept."""
    merged = []
    index = {}
    for entry in list(old_files) + list(new_files):
        rel = entry.get("rel")
        if rel in index:
            merged[index[rel]] = entry
        else:
            index[rel] = len(merged)
            merged.append(entry)
    return merged


def backup(cfg, stamp, version, paths):
    """Copy the existing content of each path (that exists) into a stamp dir.

    Returns the stamp directory path if anything was copied, else None.
    Missing paths (including dangling symlinks) are skipped silently.
    """
    backups_root = os.path.join(cfg, "backups")
    engineering_dir = os.path.join(backups_root, "engineering")
    stamp_dir = os.path.join(engineering_dir, stamp)

    files_meta = []
    stamp_created = False

    for p in paths:
        if not os.path.exists(p):
            continue
        if not stamp_created:
            _ensure_dir(cfg, 0o700)
            _ensure_dir_mode(backups_root, 0o700)
            _ensure_dir_mode(engineering_dir, 0o700)
            _ensure_dir_mode(stamp_dir, 0o700)
            stamp_created = True

        rel = os.path.relpath(p, cfg)
        was_symlink = os.path.islink(p)
        link_target = os.readlink(p) if was_symlink else None
        real = os.path.realpath(p)
        mode = "%04o" % (os.stat(real).st_mode & 0o777)
        with open(real, "rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()

        rel_posix = rel.replace(os.sep, "/")
        base_stored = rel_posix.replace("/", "__")
        if base_stored == "manifest.json":
            base_stored = "manifest.json__file"  # the stamp's own manifest owns that name
        stored = base_stored
        dest = os.path.join(stamp_dir, stored)
        i = 1
        while os.path.exists(dest):
            stored = "{}__{}".format(base_stored, i)
            dest = os.path.join(stamp_dir, stored)
            i += 1
        shutil.copy2(real, dest)

        files_meta.append(
            {
                "rel": rel_posix,
                "realpath": real,
                "mode": mode,
                "was_symlink": was_symlink,
                "link_target": link_target,
                "sha256": sha,
                "stored": stored,
            }
        )

    if not stamp_created:
        return None

    manifest_path = os.path.join(stamp_dir, "manifest.json")
    manifest = {
        "schema": SCHEMA,
        "installer_version": version,
        "stamp": stamp,
        "files": _merge_files(_existing_files(manifest_path), files_meta),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    os.chmod(manifest_path, 0o600)

    _prune(engineering_dir)

    return stamp_dir


def list_backups(cfg):
    engineering_dir = os.path.join(cfg, "backups", "engineering")
    lines = []
    for name in _list_stamps(engineering_dir):
        manifest_path = os.path.join(engineering_dir, name, "manifest.json")
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError):
            continue
        version = manifest.get("installer_version", "")
        rels = ",".join(entry.get("rel", "") for entry in manifest.get("files", []))
        lines.append("{}\t{}\t{}".format(name, version, rels))
    return lines


def _resolve_stamp_dir(engineering_dir, stamp):
    if stamp:
        if not STAMP_RE.match(stamp):
            return None
        path = os.path.join(engineering_dir, stamp)
        return path if os.path.isdir(path) else None
    names = _list_stamps(engineering_dir)
    if not names:
        return None
    return os.path.join(engineering_dir, names[-1])


def _validate_rel(rel):
    if not rel:
        return "empty path"
    if os.path.isabs(rel):
        return "absolute path not allowed"
    parts = rel.replace("\\", "/").split("/")
    if ".." in parts:
        return "path traversal ('..') not allowed"
    return None


def _validate_stored(stored):
    """`stored` must be one of the flat names backup() emits, nothing else."""
    if not isinstance(stored, str) or not stored:
        return "empty stored name in manifest"
    if (
        stored in (".", "..")
        or os.path.isabs(stored)
        or "/" in stored
        or "\\" in stored
    ):
        return "invalid stored name in manifest (must be a flat file name)"
    return None


def _sha_of_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _pre_restore_stamp():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "{}-{}".format(now, os.getpid())


def restore(cfg, stamp=None, break_hardlinks=False):
    """Restore files from a stamp directory.

    Returns 0 (all restored), 8 (any refusal), or raises SafeWriteError(9, ...)
    when there is no usable backup/manifest. Prints "restored <rel>" or
    "refused <rel>: <reason>" for each manifest entry as a side effect, after a
    "pre-restore backup: <stamp dir>" line when the current state of any target
    was saved first.
    """
    engineering_dir = os.path.join(cfg, "backups", "engineering")
    stamp_dir = _resolve_stamp_dir(engineering_dir, stamp)
    if stamp_dir is None:
        raise SafeWriteError(9, "no backups found")

    manifest_path = os.path.join(stamp_dir, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        if manifest.get("schema") != SCHEMA:
            raise ValueError("unexpected schema")
        files = manifest["files"]
        if not isinstance(files, list):
            raise ValueError("files is not a list")
    except (OSError, ValueError, KeyError) as e:
        raise SafeWriteError(9, "invalid manifest: {}".format(e))

    real_cfg = os.path.realpath(cfg)
    any_refused = False

    # Phase 1: validate every entry and read its backup copy into memory. This
    # happens before anything touches the filesystem because the pre-restore
    # backup below may prune this very stamp dir.
    plans = []
    for raw in files:
        entry = raw if isinstance(raw, dict) else {}
        rel = entry.get("rel", "")
        if not isinstance(rel, str):
            rel = ""
        reason = _validate_rel(rel)
        if reason:
            plans.append({"rel": rel, "refused": reason})
            continue

        stored = entry.get("stored", "")
        reason = _validate_stored(stored)
        if reason:
            plans.append({"rel": rel, "refused": reason})
            continue

        try:
            with open(os.path.join(stamp_dir, stored), "rb") as f:
                content = f.read()
        except OSError as e:
            plans.append(
                {"rel": rel, "refused": "cannot read backup copy: {}".format(e)}
            )
            continue

        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            plans.append(
                {
                    "rel": rel,
                    "refused": "stored backup copy sha256 mismatch (tampered "
                    "manifest or backup)",
                }
            )
            continue

        try:
            mode = int(entry.get("mode", "0600"), 8) & 0o777
        except (TypeError, ValueError):
            plans.append({"rel": rel, "refused": "invalid mode in manifest"})
            continue

        plans.append(
            {
                "rel": rel,
                "entry": entry,
                "content": content,
                "mode": mode,
                "target": os.path.join(cfg, rel),
            }
        )

    # Phase 2: save the current state of every target we are about to write, so
    # a restore never silently discards post-backup edits.
    targets = [plan["target"] for plan in plans if "target" in plan]
    if targets:
        version = manifest.get("installer_version", "")
        if not isinstance(version, str):
            version = ""
        try:
            pre_dir = backup(cfg, _pre_restore_stamp(), version, targets)
        except OSError as exc:
            print("refused: pre-restore backup failed ({}); nothing restored".format(exc))
            return 8
        if pre_dir:
            print("pre-restore backup: {}".format(pre_dir))

    # Phase 3: restore.
    for plan in plans:
        rel = plan["rel"]
        if "refused" in plan:
            print("refused {}: {}".format(rel, plan["refused"]))
            any_refused = True
            continue

        entry = plan["entry"]
        target = plan["target"]
        content = plan["content"]
        mode = plan["mode"]

        link_target = entry.get("link_target")
        recorded_real = None

        if bool(entry.get("was_symlink")) and isinstance(link_target, str) and link_target:
            if os.path.isabs(link_target):
                recorded_real = os.path.realpath(link_target)
            else:
                recorded_real = os.path.realpath(
                    os.path.join(os.path.dirname(target), link_target)
                )
            if not os.path.lexists(target):
                # The link is gone. Recreate it only when the recorded target
                # still holds exactly the backed-up bytes; then the content is
                # already correct and nothing is written. Otherwise refuse: a
                # manifest must never be able to create files or directories
                # outside $CFG.
                if _sha_of_file(recorded_real) != entry.get("sha256"):
                    print(
                        "refused {}: recorded symlink target {} is missing or "
                        "modified; not recreated".format(rel, link_target)
                    )
                    any_refused = True
                    continue
                parent = os.path.dirname(target)
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent, mode=0o755)
                    os.chmod(parent, 0o755)
                try:
                    os.symlink(link_target, target)
                except OSError as e:
                    print("refused {}: {}".format(rel, e))
                    any_refused = True
                    continue
                print("restored {}".format(rel))
                continue

        real_target = os.path.realpath(target)
        inside_cfg = real_target == real_cfg or real_target.startswith(
            real_cfg + os.sep
        )
        if not inside_cfg:
            # An intact symlink may still point outside $CFG, but only at the
            # exact location recorded at backup time.
            if recorded_real is None or real_target != recorded_real:
                print("refused {}: restore target escapes $CFG".format(rel))
                any_refused = True
                continue

        try:
            write_target(
                target,
                content,
                mode,
                break_hardlinks=break_hardlinks,
                create_through_dangling=True,
            )
            os.chmod(os.path.realpath(target), mode)
        except SafeWriteError as e:
            print("refused {}: {}".format(rel, e.message))
            any_refused = True
            continue
        except OSError as e:
            print("refused {}: {}".format(rel, e))
            any_refused = True
            continue

        print("restored {}".format(rel))

    return 8 if any_refused else 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _write_cmd(args):
    if args.from_path == "-":
        content = sys.stdin.buffer.read()
    else:
        with open(args.from_path, "rb") as f:
            content = f.read()
    default_mode = int(args.default_mode, 8)
    result = write_target(
        args.target,
        content,
        default_mode,
        break_hardlinks=args.break_hardlinks,
        create_through_dangling=args.create_through_dangling,
        cfg=args.cfg,
    )
    print(result)
    return 0


def _backup_cmd(args):
    result = backup(args.cfg, args.stamp, args.version, args.paths)
    if result:
        print(result)
    return 0


def _restore_cmd(args):
    return restore(args.cfg, args.stamp, args.break_hardlinks)


def _list_cmd(args):
    for line in list_backups(args.cfg):
        print(line)
    return 0


def _check_cmd(args):
    check_target(args.target, break_hardlinks=False)
    return 0


def _mode_cmd(args):
    if not os.path.exists(args.target):
        print("absent")
        return 0
    real = os.path.realpath(args.target)
    if not os.path.exists(real):
        print("absent")
        return 0
    m = stat.S_IMODE(os.stat(real).st_mode)
    print("%04o" % m)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="safe_write.py")
    sub = p.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write")
    w.add_argument("--target", required=True)
    w.add_argument("--from", dest="from_path", required=True)
    w.add_argument("--default-mode", required=True, choices=["0600", "0644"])
    w.add_argument("--break-hardlinks", action="store_true")
    w.add_argument("--create-through-dangling", action="store_true")
    w.add_argument("--cfg", default=None)
    w.set_defaults(func=_write_cmd)

    b = sub.add_parser("backup")
    b.add_argument("--cfg", required=True)
    b.add_argument("--stamp", required=True)
    b.add_argument("--version", required=True)
    b.add_argument("paths", nargs="*")
    b.set_defaults(func=_backup_cmd)

    r = sub.add_parser("restore")
    r.add_argument("--cfg", required=True)
    r.add_argument("--stamp")
    r.add_argument("--break-hardlinks", action="store_true")
    r.set_defaults(func=_restore_cmd)

    l = sub.add_parser("list")
    l.add_argument("--cfg", required=True)
    l.set_defaults(func=_list_cmd)

    c = sub.add_parser("check")
    c.add_argument("--target", required=True)
    c.set_defaults(func=_check_cmd)

    m = sub.add_parser("mode")
    m.add_argument("--target", required=True)
    m.set_defaults(func=_mode_cmd)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SafeWriteError as e:
        print(e.message, file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
