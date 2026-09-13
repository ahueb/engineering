"""Safe, atomic file writes plus structured backup/restore for the installer.

Python >= 3.8, stdlib only. The exact behaviour of each subcommand is documented
below and in scripts/tests/test_safe_write.py.

Subcommands: write, backup, mark-written, restore, list, check, mode.
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

# Install stamps are YYYYMMDDTHHMMSS.ffffffZ-<pid>; the second-resolution form
# YYYYMMDDTHHMMSSZ-<pid> written by installers before 2.9.0 is still accepted.
STAMP_RE = re.compile(r"^\d{8}T\d{6}(?:\.\d{6})?Z-\d+$")
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
    """Sort key for a stamp dir: (datetime, numeric pid), not lexicographic.

    Both stamp forms parse; a legacy second-resolution stamp is padded to
    `.000000`, so it sorts below a microsecond stamp of the same second.
    """
    ts, _, pid = name.rpartition("-")
    try:
        pid_num = int(pid)
    except ValueError:
        pid_num = 0
    core = ts[:-1] if ts.endswith("Z") else ts
    if "." not in core:
        core += ".000000"
    try:
        when = datetime.datetime.strptime(core, "%Y%m%dT%H%M%S.%f")
    except ValueError:
        when = datetime.datetime.min
    return (when, pid_num)


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


def _prune(engineering_dir, keep=5, protect=None):
    """Keep the `keep` newest stamp dirs, but never remove the one named `protect`.

    `protect` is the stamp the caller just wrote to; without this, five
    pre-existing stamps (however they sort relative to it) could prune the
    run's own stamp on its first write. `protect` still counts toward `keep`
    when present, so the total stays bounded the same way it always has.
    """
    names = _list_stamps(engineering_dir)
    if len(names) <= keep:
        return
    removable = [n for n in names if n != protect]
    for old in removable[: len(names) - keep]:
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
    """Merge manifest entries, keyed by `rel`; order kept.

    Merging is per field: an entry for a `rel` that already exists keeps every
    field the newer entry does not carry (so a `backup()` never drops the
    `written_sha256`/`created`/`removed` fields a `mark-written` recorded, and
    a `mark-written` never drops `stored`/`sha256`/`mode`/`link_target`).
    """
    merged = []
    index = {}
    for entry in list(old_files) + list(new_files):
        rel = entry.get("rel")
        if rel in index:
            combined = dict(merged[index[rel]])
            combined.update(entry)
            merged[index[rel]] = combined
        else:
            index[rel] = len(merged)
            merged.append(dict(entry))
    return merged


def _write_manifest(stamp_dir, stamp, version, files):
    manifest_path = os.path.join(stamp_dir, "manifest.json")
    manifest = {
        "schema": SCHEMA,
        "installer_version": version,
        "stamp": stamp,
        "files": files,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    os.chmod(manifest_path, 0o600)
    return manifest_path


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
    _write_manifest(
        stamp_dir, stamp, version, _merge_files(_existing_files(manifest_path), files_meta)
    )

    _prune(engineering_dir, protect=stamp)

    return stamp_dir


def mark_written(cfg, stamp, version, rel, written_sha, created=False, removed=False):
    """Record that this run wrote (or removed) `rel`, merging into its entry.

    Creates the stamp directory and a manifest when the run has backed up
    nothing yet, so a rollback can find files that were created rather than
    overwritten. Returns the stamp directory.
    """
    backups_root = os.path.join(cfg, "backups")
    engineering_dir = os.path.join(backups_root, "engineering")
    stamp_dir = os.path.join(engineering_dir, stamp)

    _ensure_dir(cfg, 0o700)
    _ensure_dir_mode(backups_root, 0o700)
    _ensure_dir_mode(engineering_dir, 0o700)
    _ensure_dir_mode(stamp_dir, 0o700)

    rel_posix = rel.replace(os.sep, "/")
    entry = {
        "rel": rel_posix,
        "written_sha256": written_sha,
        "created": bool(created),
        "removed": bool(removed),
    }
    if created:
        # The live path decides how a created file is undone: a symlink this run
        # created through is unlinked itself, never its target.
        live = os.path.join(cfg, rel)
        was_symlink = os.path.islink(live)
        entry["was_symlink"] = was_symlink
        entry["link_target"] = os.readlink(live) if was_symlink else None

    manifest_path = os.path.join(stamp_dir, "manifest.json")
    _write_manifest(
        stamp_dir, stamp, version, _merge_files(_existing_files(manifest_path), [entry])
    )

    _prune(engineering_dir, protect=stamp)

    return stamp_dir


def _marked_written(cfg, stamp):
    """True when any entry of `stamp` (or the newest stamp) carries written_sha256."""
    engineering_dir = os.path.join(cfg, "backups", "engineering")
    stamp_dir = _resolve_stamp_dir(engineering_dir, stamp)
    if stamp_dir is None:
        return False
    for entry in _existing_files(os.path.join(stamp_dir, "manifest.json")):
        value = entry.get("written_sha256")
        if isinstance(value, str) and value:
            return True
    return False


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
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return "{}-{}".format(now, os.getpid())


def _recorded_link_real(entry, target):
    """Real path of the symlink target recorded for `entry`, or None."""
    link_target = entry.get("link_target")
    if not bool(entry.get("was_symlink")):
        return None
    if not isinstance(link_target, str) or not link_target:
        return None
    if os.path.isabs(link_target):
        return os.path.realpath(link_target)
    return os.path.realpath(os.path.join(os.path.dirname(target), link_target))


def _effective_real(entry, target):
    """Where a restore of `entry` would actually land.

    The live path decides while it exists (an intact symlink wins over the
    manifest); otherwise the recorded link target is what would be recreated.
    """
    if os.path.lexists(target):
        return os.path.realpath(target)
    recorded = _recorded_link_real(entry, target)
    return recorded if recorded is not None else os.path.realpath(target)


def _inside(real_cfg, path):
    return path == real_cfg or path.startswith(real_cfg + os.sep)


def restore(
    cfg,
    stamp=None,
    break_hardlinks=False,
    only_run_files=False,
    no_outside_cfg=False,
):
    """Restore files from a stamp directory.

    Returns 0 (all restored), 8 (any refusal), or raises SafeWriteError(9, ...)
    when there is no usable backup/manifest, or SafeWriteError(12, ...) when
    `only_run_files` is set and the stamp marks nothing as written. Prints
    "restored <rel>", "deleted <rel>", "refused <rel>: <reason>" or
    "not rolled back: <rel> changed after this run wrote it" for each manifest
    entry as a side effect, after the "outside config dir: <rel> -> <real>"
    disclosure lines and a "pre-restore backup: <stamp dir>" line when the
    current state of any target was saved first.

    `only_run_files` restricts the work to entries this run marked with
    `mark-written` and leaves anything changed since that write alone.
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

    entries = [raw if isinstance(raw, dict) else {} for raw in files]
    if only_run_files and not any(
        isinstance(e.get("written_sha256"), str) and e.get("written_sha256")
        for e in entries
    ):
        raise SafeWriteError(
            12, "no file in this stamp was marked as written by an installer run"
        )

    # Phase 1: validate every entry and read its backup copy into memory. This
    # happens before anything touches the filesystem because the pre-restore
    # backup below may prune this very stamp dir.
    plans = []
    for entry in entries:
        rel = entry.get("rel", "")
        if not isinstance(rel, str):
            rel = ""
        written_sha = entry.get("written_sha256")
        if not isinstance(written_sha, str):
            written_sha = ""
        created = bool(entry.get("created"))

        if only_run_files:
            if not written_sha:
                continue
        elif created:
            # A file this run created has no backup copy: a plain restore puts
            # the recorded files back and leaves everything else alone.
            continue

        reason = _validate_rel(rel)
        if reason:
            plans.append({"rel": rel, "refused": reason})
            continue

        if only_run_files and created:
            plans.append(
                {
                    "rel": rel,
                    "entry": entry,
                    "action": "delete",
                    "written_sha": written_sha,
                    "target": os.path.join(cfg, rel),
                }
            )
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
                "action": "restore",
                "written_sha": written_sha,
                "content": content,
                "mode": mode,
                "target": os.path.join(cfg, rel),
            }
        )

    # Disclosure: every entry whose real target lies outside the config dir is
    # named before anything is written; --no-outside-cfg refuses those entries.
    for plan in plans:
        if "target" not in plan or "refused" in plan:
            continue
        real = _effective_real(plan["entry"], plan["target"])
        if _inside(real_cfg, real):
            continue
        print("outside config dir: {} -> {}".format(plan["rel"], real))
        if no_outside_cfg:
            plan["refused"] = "outside config dir"

    # Phase 2: save the current state of every target we are about to write, so
    # a restore never silently discards post-backup edits.
    targets = [
        plan["target"] for plan in plans if "target" in plan and "refused" not in plan
    ]
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
        recorded_real = _recorded_link_real(entry, target)

        if plan["action"] == "delete":
            # A file this run created: undo it only when it still holds exactly
            # the bytes this run wrote, and only inside $CFG (or at the exact
            # link target recorded when it was written).
            if _sha_of_file(os.path.realpath(target)) != plan["written_sha"]:
                print(
                    "not rolled back: {} changed after this run wrote it".format(rel)
                )
                continue
            real_target = os.path.realpath(target)
            if not _inside(real_cfg, real_target) and real_target != recorded_real:
                print("refused {}: delete target escapes $CFG".format(rel))
                any_refused = True
                continue
            try:
                os.unlink(target)  # the path itself; a symlink's target is kept
            except OSError as e:
                print("refused {}: {}".format(rel, e))
                any_refused = True
                continue
            print("deleted {}".format(rel))
            continue

        if only_run_files:
            if bool(entry.get("removed")):
                if os.path.lexists(target):
                    print(
                        "not rolled back: {} changed after this run wrote it".format(
                            rel
                        )
                    )
                    continue
            elif _sha_of_file(os.path.realpath(target)) != plan["written_sha"]:
                print("not rolled back: {} changed after this run wrote it".format(rel))
                continue

        content = plan["content"]
        mode = plan["mode"]
        link_target = entry.get("link_target")

        if recorded_real is not None:
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
        inside_cfg = _inside(real_cfg, real_target)
        create_through_dangling = True
        if not inside_cfg:
            if recorded_real is not None and real_target == recorded_real:
                # The entry's own symlink is intact and still points at the exact
                # location recorded at backup time. If that target is now missing
                # (a dangling symlink), refuse rather than create a file (and any
                # missing parent directories) outside $CFG.
                if not os.path.exists(real_target):
                    print(
                        "refused {}: symlink target {} outside $CFG is missing; "
                        "not created".format(rel, real_target)
                    )
                    any_refused = True
                    continue
                create_through_dangling = False
            elif recorded_real is None and os.path.lexists(target):
                # Not a symlink entry itself, but it resolves outside $CFG because a
                # parent directory is a symlink (already disclosed above). Restore
                # only over a path that already exists there; never create one.
                create_through_dangling = False
            else:
                print("refused {}: restore target escapes $CFG".format(rel))
                any_refused = True
                continue

        try:
            write_target(
                target,
                content,
                mode,
                break_hardlinks=break_hardlinks,
                create_through_dangling=create_through_dangling,
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


def _mark_written_cmd(args):
    mark_written(
        args.cfg,
        args.stamp,
        args.version,
        args.rel,
        args.written_sha,
        created=args.created,
        removed=args.removed,
    )
    return 0


def _restore_cmd(args):
    return restore(
        args.cfg,
        args.stamp,
        args.break_hardlinks,
        only_run_files=args.only_run_files,
        no_outside_cfg=args.no_outside_cfg,
    )


def _list_cmd(args):
    if args.written:
        # Predicate only: no output, exit 0 when this run wrote something.
        return 0 if _marked_written(args.cfg, args.stamp) else 1
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

    mw = sub.add_parser("mark-written")
    mw.add_argument("--cfg", required=True)
    mw.add_argument("--stamp", required=True)
    mw.add_argument("--version", required=True)
    mw.add_argument("--rel", required=True)
    mw.add_argument("--written-sha", dest="written_sha", required=True)
    kind = mw.add_mutually_exclusive_group()
    kind.add_argument("--created", action="store_true")
    kind.add_argument("--removed", action="store_true")
    mw.set_defaults(func=_mark_written_cmd)

    r = sub.add_parser("restore")
    r.add_argument("--cfg", required=True)
    r.add_argument("--stamp")
    r.add_argument("--break-hardlinks", action="store_true")
    r.add_argument("--only-run-files", dest="only_run_files", action="store_true")
    r.add_argument("--no-outside-cfg", dest="no_outside_cfg", action="store_true")
    r.set_defaults(func=_restore_cmd)

    l = sub.add_parser("list")
    l.add_argument("--cfg", required=True)
    l.add_argument("--stamp")
    l.add_argument("--written", action="store_true")
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
