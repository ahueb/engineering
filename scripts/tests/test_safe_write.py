import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import safe_write  # noqa: E402


POSIX_ONLY = unittest.skipUnless(os.name == "posix", "mode/umask semantics are POSIX-only")
# Windows symlink resolution (short 8.3 names, junction semantics) and replacing an open file
# are out of scope for the installer on Windows (risk register R5); the behaviour is only
# specified for POSIX.
SYMLINKS_POSIX_ONLY = unittest.skipUnless(os.name == "posix", "symlink semantics are POSIX-only (risk register R5)")
REPLACE_OPEN_POSIX_ONLY = unittest.skipUnless(os.name == "posix", "replacing an open file is refused on Windows (exit 7)")


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


class WriteTests(TempDirCase):
    @POSIX_ONLY
    def test_new_file_default_mode_0600(self):
        target = self.root / "settings.json"
        result = safe_write.write_target(str(target), b'{"a":1}', 0o600)
        self.assertEqual(result, "written")
        self.assertEqual(target.read_bytes(), b'{"a":1}')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    @POSIX_ONLY
    def test_new_file_default_mode_0644(self):
        target = self.root / "rules" / "engineering-policy.md"
        result = safe_write.write_target(str(target), b"policy", 0o644)
        self.assertEqual(result, "written")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    @POSIX_ONLY
    def test_existing_mode_0600_preserved(self):
        target = self.root / "f.json"
        target.write_bytes(b"old")
        os.chmod(target, 0o600)
        safe_write.write_target(str(target), b"new", 0o644)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(target.read_bytes(), b"new")

    def test_unchanged_when_content_identical(self):
        target = self.root / "f.json"
        target.write_bytes(b"same")
        result = safe_write.write_target(str(target), b"same", 0o600)
        self.assertEqual(result, "unchanged")

    @POSIX_ONLY
    def test_umask_077_applies_only_to_new_file_default_mode(self):
        old = os.umask(0o077)
        try:
            target = self.root / "u.json"
            safe_write.write_target(str(target), b"x", 0o644)
            # write_target chmods explicitly to the requested mode; umask must
            # not narrow it since we set mode via os.chmod, not open().
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
        finally:
            os.umask(old)

    @POSIX_ONLY
    def test_umask_022_applies_only_to_new_file_default_mode(self):
        old = os.umask(0o022)
        try:
            target = self.root / "u2.json"
            safe_write.write_target(str(target), b"x", 0o600)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        finally:
            os.umask(old)

    @SYMLINKS_POSIX_ONLY
    def test_symlinked_file_kept_target_updated(self):
        real = self.root / "real.json"
        real.write_bytes(b"old")
        link = self.root / "settings.json"
        link.symlink_to(real)
        result = safe_write.write_target(str(link), b"new", 0o600)
        self.assertEqual(result, "written")
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(str(link)), str(real))
        self.assertEqual(real.read_bytes(), b"new")

    def test_symlinked_parent_dir(self):
        real_dir = self.root / "real_rules"
        real_dir.mkdir()
        link_dir = self.root / "rules"
        link_dir.symlink_to(real_dir)
        target = link_dir / "engineering-policy.md"
        result = safe_write.write_target(str(target), b"policy", 0o644)
        self.assertEqual(result, "written")
        self.assertEqual((real_dir / "engineering-policy.md").read_bytes(), b"policy")

    @POSIX_ONLY
    def test_hard_link_refused_then_broken_with_flag(self):
        target = self.root / "settings.json"
        target.write_bytes(b"old")
        other = self.root / "other-link.json"
        os.link(str(target), str(other))
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.write_target(str(target), b"new", 0o600)
        self.assertEqual(ctx.exception.code, 5)
        # untouched
        self.assertEqual(target.read_bytes(), b"old")

        result = safe_write.write_target(
            str(target), b"new", 0o600, break_hardlinks=True
        )
        self.assertEqual(result, "written")
        self.assertEqual(target.read_bytes(), b"new")
        # other name kept its old content (hard link detached, not corrupted)
        self.assertEqual(other.read_bytes(), b"old")

    def test_dangling_symlink_refused_then_created(self):
        missing_real = self.root / "nowhere.json"
        link = self.root / "settings.json"
        link.symlink_to(missing_real)

        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.write_target(str(link), b"x", 0o600)
        self.assertEqual(ctx.exception.code, 4)

        result = safe_write.write_target(
            str(link), b"x", 0o600, create_through_dangling=True
        )
        self.assertEqual(result, "written")
        self.assertEqual(missing_real.read_bytes(), b"x")

    @POSIX_ONLY
    def test_directory_refused(self):
        target = self.root / "adir"
        target.mkdir()
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.write_target(str(target), b"x", 0o600)
        self.assertEqual(ctx.exception.code, 4)

    @POSIX_ONLY
    def test_fifo_refused(self):
        target = self.root / "afifo"
        os.mkfifo(str(target))
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.write_target(str(target), b"x", 0o600)
        self.assertEqual(ctx.exception.code, 4)

    def test_temp_file_removed_after_injected_write_failure(self):
        target = self.root / "f.json"
        target.write_bytes(b"old")

        def boom(src, dst):
            raise OSError("injected failure")

        with mock.patch.object(safe_write.os, "replace", side_effect=boom):
            with self.assertRaises(safe_write.SafeWriteError) as ctx:
                safe_write.write_target(str(target), b"new", 0o600)
        self.assertEqual(ctx.exception.code, 6)
        self.assertEqual(target.read_bytes(), b"old")
        leftover = [
            p for p in self.root.iterdir() if p.name not in ("f.json",)
        ]
        self.assertEqual(leftover, [])

    @REPLACE_OPEN_POSIX_ONLY
    def test_concurrent_reader_on_old_fd_sees_old_bytes(self):
        target = self.root / "f.json"
        target.write_bytes(b"old-bytes")
        fd = open(str(target), "rb")
        try:
            safe_write.write_target(str(target), b"new-bytes", 0o600)
            # the old fd still refers to the unlinked/replaced inode
            self.assertEqual(fd.read(), b"old-bytes")
            with open(str(target), "rb") as f2:
                self.assertEqual(f2.read(), b"new-bytes")
        finally:
            fd.close()


class CheckModeCliTests(TempDirCase):
    def test_check_missing_ok(self):
        target = self.root / "nope.json"
        # check_target should not raise for a missing target
        safe_write.check_target(str(target))

    @POSIX_ONLY
    def test_check_hardlink_exit5(self):
        target = self.root / "f.json"
        target.write_bytes(b"x")
        os.link(str(target), str(self.root / "g.json"))
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.check_target(str(target))
        self.assertEqual(ctx.exception.code, 5)

    def test_mode_cmd_absent_and_present(self):
        target = self.root / "nope.json"
        rc = safe_write.main(["mode", "--target", str(target)])
        self.assertEqual(rc, 0)

        target.write_bytes(b"x")
        if os.name == "posix":
            os.chmod(target, 0o600)
            captured = []
            with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
                safe_write.main(["mode", "--target", str(target)])
            self.assertEqual(captured[-1], "0600")


class BackupTests(TempDirCase):
    def test_backup_of_only_missing_paths_creates_no_stamp_dir(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        missing1 = cfg / "settings.json"
        missing2 = cfg / "rules" / "engineering-policy.md"
        result = safe_write.backup(
            str(cfg), "20260101T000000Z-1", "1.0.0", [str(missing1), str(missing2)]
        )
        self.assertIsNone(result)
        self.assertFalse((cfg / "backups").exists())

    @POSIX_ONLY
    def test_backup_creates_0700_dirs_and_manifest(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b'{"a":1}')
        os.chmod(settings, 0o600)

        stamp_dir = safe_write.backup(
            str(cfg), "20260101T000000Z-1", "1.0.0", [str(settings)]
        )
        self.assertIsNotNone(stamp_dir)
        self.assertEqual(
            stat.S_IMODE(os.stat(cfg / "backups" / "engineering").st_mode), 0o700
        )
        self.assertEqual(stat.S_IMODE(os.stat(stamp_dir).st_mode), 0o700)

        manifest = json.loads((Path(stamp_dir) / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(len(manifest["files"]), 1)
        entry = manifest["files"][0]
        self.assertEqual(entry["rel"], "settings.json")
        self.assertEqual(entry["mode"], "0600")
        self.assertFalse(entry["was_symlink"])
        self.assertIsNone(entry["link_target"])
        self.assertEqual(
            entry["sha256"], safe_write.hashlib.sha256(b'{"a":1}').hexdigest()
        )

    def test_prune_keeps_newest_5_mixed_order_ignores_non_matching(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)

        stamps = [
            "20260101T000000Z-100",
            "20260103T000000Z-100",
            "20260102T000000Z-100",
            "20260105T000000Z-100",
            "20260104T000000Z-100",
            "20260106T000000Z-100",
        ]
        # create in mixed (non-chronological) insertion order
        for s in stamps:
            (eng / s).mkdir()
            (eng / s / "manifest.json").write_text(
                json.dumps({"schema": 1, "installer_version": "x", "files": []})
            )
        (eng / "not-a-stamp").mkdir()
        (eng / "stray-file.txt").write_text("hi")

        safe_write._prune(eng)

        remaining = sorted(p.name for p in eng.iterdir() if p.is_dir())
        self.assertIn("not-a-stamp", remaining)
        stamp_remaining = sorted(n for n in remaining if safe_write.STAMP_RE.match(n))
        self.assertEqual(
            stamp_remaining,
            [
                "20260102T000000Z-100",
                "20260103T000000Z-100",
                "20260104T000000Z-100",
                "20260105T000000Z-100",
                "20260106T000000Z-100",
            ],
        )
        self.assertTrue((eng / "stray-file.txt").exists())

    def test_two_backups_same_stamp_merge_instead_of_overwrite(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b'{"a":1}')
        claude = cfg / "CLAUDE.md"
        claude.write_bytes(b"policy")

        stamp = "20260101T000000Z-1"
        safe_write.backup(str(cfg), stamp, "1.0.0", [str(settings)])
        stamp_dir = Path(
            safe_write.backup(str(cfg), stamp, "1.0.0", [str(claude)])
        )

        manifest = json.loads((stamp_dir / "manifest.json").read_text())
        rels = sorted(e["rel"] for e in manifest["files"])
        self.assertEqual(rels, ["CLAUDE.md", "settings.json"])
        by_rel = {e["rel"]: e for e in manifest["files"]}
        self.assertEqual(
            (stamp_dir / by_rel["settings.json"]["stored"]).read_bytes(), b'{"a":1}'
        )
        self.assertEqual(
            (stamp_dir / by_rel["CLAUDE.md"]["stored"]).read_bytes(), b"policy"
        )

    def test_same_rel_backed_up_twice_in_one_stamp_keeps_latest(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b"first")
        stamp = "20260101T000000Z-1"
        safe_write.backup(str(cfg), stamp, "1.0.0", [str(settings)])
        settings.write_bytes(b"second")
        stamp_dir = Path(safe_write.backup(str(cfg), stamp, "1.0.0", [str(settings)]))

        manifest = json.loads((stamp_dir / "manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), 1)
        entry = manifest["files"][0]
        self.assertEqual(
            entry["sha256"], safe_write.hashlib.sha256(b"second").hexdigest()
        )
        self.assertEqual((stamp_dir / entry["stored"]).read_bytes(), b"second")

    def test_backup_of_only_missing_paths_does_not_create_cfg(self):
        cfg = self.root / "cfg"
        result = safe_write.backup(
            str(cfg), "20260101T000000Z-1", "1.0.0", [str(cfg / "settings.json")]
        )
        self.assertIsNone(result)
        self.assertFalse(cfg.exists())

    def test_stamps_sorted_by_numeric_pid_not_string(self):
        cfg = self.root / "cfg"
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)
        names = [
            "20260101T000000Z-2",
            "20260101T000000Z-10",
            "20260101T000000Z-9",
        ]
        for n in names:
            (eng / n).mkdir()
        self.assertEqual(
            safe_write._list_stamps(str(eng)),
            ["20260101T000000Z-2", "20260101T000000Z-9", "20260101T000000Z-10"],
        )

    def test_prune_drops_lowest_numeric_pid_stamp(self):
        cfg = self.root / "cfg"
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)
        names = [
            "20260101T000000Z-2",
            "20260101T000000Z-10",
            "20260101T000000Z-11",
            "20260101T000000Z-12",
            "20260101T000000Z-13",
            "20260101T000000Z-14",
        ]
        for n in names:
            (eng / n).mkdir()
        safe_write._prune(str(eng))
        remaining = sorted(p.name for p in eng.iterdir())
        self.assertNotIn("20260101T000000Z-2", remaining)
        self.assertEqual(len(remaining), 5)

    def test_marker_file_never_listed_or_pruned(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        marker = cfg / "engineering-installer.json"
        marker.write_text(json.dumps({"schema": 1}))

        settings = cfg / "settings.json"
        settings.write_bytes(b"x")
        safe_write.backup(str(cfg), "20260101T000000Z-1", "1.0.0", [str(settings)])

        lines = safe_write.list_backups(str(cfg))
        self.assertEqual(len(lines), 1)
        for line in lines:
            self.assertNotIn("engineering-installer.json", line)

        # marker still present and untouched by backup/prune
        self.assertTrue(marker.exists())


class RestoreTests(TempDirCase):
    def _make_cfg_with_backup(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b'{"a":1}')
        os.chmod(settings, 0o600)
        stamp = "20260101T000000Z-1"
        safe_write.backup(str(cfg), stamp, "1.0.0", [str(settings)])
        return cfg, stamp

    @POSIX_ONLY
    def test_restore_byte_identical_with_mode(self):
        cfg, stamp = self._make_cfg_with_backup()
        settings = cfg / "settings.json"
        settings.write_bytes(b"corrupted")
        os.chmod(settings, 0o644)

        rc = safe_write.restore(str(cfg))
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b'{"a":1}')
        self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)

    def test_restore_refuses_dotdot_absolute_and_tampered_sha(self):
        cfg, stamp = self._make_cfg_with_backup()
        stamp_dir = cfg / "backups" / "engineering" / stamp
        manifest_path = stamp_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        bad_entries = []
        for rel in ("../evil.json", "/etc/passwd"):
            entry = dict(manifest["files"][0])
            entry["rel"] = rel
            bad_entries.append(entry)

        tampered_sha_entry = dict(manifest["files"][0])
        tampered_sha_entry["sha256"] = "0" * 64
        bad_entries.append(tampered_sha_entry)

        manifest["files"] = bad_entries
        manifest_path.write_text(json.dumps(manifest))

        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 8)
        # nothing outside cfg or at absolute paths got written
        self.assertFalse((self.root / "evil.json").exists())

    @SYMLINKS_POSIX_ONLY
    def test_restore_recreates_missing_symlink_only_when_target_unchanged(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside_dir = self.root / "outside"
        outside_dir.mkdir()
        real_target = outside_dir / "CLAUDE.md"
        real_target.write_bytes(b"policy content")

        link = cfg / "CLAUDE.md"
        link.symlink_to(real_target)

        stamp = "20260101T000000Z-1"
        safe_write.backup(str(cfg), stamp, "1.0.0", [str(link)])

        # link removed, recorded target still byte-identical: link is recreated
        # and nothing is written (content already matches).
        link.unlink()
        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(real_target.read_bytes(), b"policy content")

        # link removed and recorded target edited since the backup: refuse, and
        # do not recreate the link.
        link.unlink()
        real_target.write_bytes(b"user edited this")
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc2 = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc2, 8)
        self.assertFalse(link.exists())
        self.assertFalse(link.is_symlink())
        self.assertEqual(real_target.read_bytes(), b"user edited this")
        self.assertTrue(
            any("is missing or modified; not recreated" in line for line in captured),
            captured,
        )

        # with the link intact, an explicit restore reverts the target as requested
        link.symlink_to(real_target)
        rc3 = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc3, 0)
        self.assertEqual(real_target.read_bytes(), b"policy content")

    def test_restore_missing_symlink_cannot_create_files_outside_cfg(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        victim_dir = self.root / "outside"
        victim = victim_dir / "sub" / "authorized_keys"

        # a real backup of an ordinary in-$CFG file, then a tampered manifest
        # claiming it was a symlink to a path that does not exist at all
        settings = cfg / "settings.json"
        settings.write_bytes(b"pwned")
        stamp = "20260101T000000Z-1"
        safe_write.backup(str(cfg), stamp, "1.0.0", [str(settings)])
        settings.unlink()

        manifest_path = cfg / "backups" / "engineering" / stamp / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][0]["was_symlink"] = True
        manifest["files"][0]["link_target"] = str(victim)
        manifest_path.write_text(json.dumps(manifest))

        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 8)
        self.assertFalse(victim.exists())
        self.assertFalse(victim.parent.exists())
        self.assertFalse(victim_dir.exists())
        self.assertFalse(settings.exists())

    def test_restore_refuses_non_flat_stored_name(self):
        cfg, stamp = self._make_cfg_with_backup()
        outside = self.root / "outside.txt"
        outside.write_bytes(b"secret")

        manifest_path = cfg / "backups" / "engineering" / stamp / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        entry = manifest["files"][0]
        for bad in ("../../../outside.txt", "/etc/passwd", "..", "sub\\x"):
            entry["stored"] = bad
            manifest_path.write_text(json.dumps(manifest))
            captured = []
            with mock.patch(
                "builtins.print", side_effect=lambda *a: captured.append(a[0])
            ):
                rc = safe_write.restore(str(cfg), stamp=stamp)
            self.assertEqual(rc, 8, bad)
            self.assertTrue(
                any("stored name in manifest" in line for line in captured), captured
            )

    @POSIX_ONLY
    def test_restore_masks_setuid_bits_from_manifest_mode(self):
        cfg, stamp = self._make_cfg_with_backup()
        manifest_path = cfg / "backups" / "engineering" / stamp / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][0]["mode"] = "6755"
        manifest_path.write_text(json.dumps(manifest))

        (cfg / "settings.json").write_bytes(b"corrupted")
        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        mode = os.stat(str(cfg / "settings.json")).st_mode
        self.assertEqual(stat.S_IMODE(mode), 0o755)
        self.assertFalse(mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX))

    def test_restore_takes_pre_restore_backup_of_current_state(self):
        cfg, stamp = self._make_cfg_with_backup()
        settings = cfg / "settings.json"
        settings.write_bytes(b"post-backup user edit")

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b'{"a":1}')

        pre_lines = [l for l in captured if l.startswith("pre-restore backup: ")]
        self.assertEqual(len(pre_lines), 1, captured)
        pre_dir = Path(pre_lines[0].split(": ", 1)[1])
        self.assertTrue(pre_dir.is_dir())
        self.assertNotEqual(pre_dir.name, stamp)

        pre_manifest = json.loads((pre_dir / "manifest.json").read_text())
        self.assertEqual([e["rel"] for e in pre_manifest["files"]], ["settings.json"])
        stored = pre_dir / pre_manifest["files"][0]["stored"]
        self.assertEqual(stored.read_bytes(), b"post-backup user edit")

    def test_no_pre_restore_backup_when_no_target_exists(self):
        cfg, stamp = self._make_cfg_with_backup()
        (cfg / "settings.json").unlink()
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual([l for l in captured if l.startswith("pre-restore backup")], [])

    @POSIX_ONLY
    def test_restore_break_hardlinks_onto_hardlinked_target(self):
        cfg, stamp = self._make_cfg_with_backup()
        settings = cfg / "settings.json"
        other = cfg / "other.json"
        os.link(str(settings), str(other))
        settings.write_bytes(b"changed-through-link")

        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 8)

        rc2 = safe_write.restore(str(cfg), stamp=stamp, break_hardlinks=True)
        self.assertEqual(rc2, 0)
        self.assertEqual(settings.read_bytes(), b'{"a":1}')

    def test_restore_no_backups_raises_exit_9(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.restore(str(cfg))
        self.assertEqual(ctx.exception.code, 9)

    def test_marker_file_never_restored(self):
        cfg, stamp = self._make_cfg_with_backup()
        marker = cfg / "engineering-installer.json"
        marker.write_text(json.dumps({"schema": 1, "should": "stay"}))
        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(
            json.loads(marker.read_text()), {"schema": 1, "should": "stay"}
        )


class StampFormTests(TempDirCase):
    def test_stamp_re_accepts_both_forms(self):
        self.assertTrue(safe_write.STAMP_RE.match("20260101T000000Z-1"))
        self.assertTrue(safe_write.STAMP_RE.match("20260101T000000.123456Z-1"))
        self.assertFalse(safe_write.STAMP_RE.match("20260101T000000.123Z-1"))
        self.assertFalse(safe_write.STAMP_RE.match("20260101T000000Z"))

    def test_pre_restore_stamp_is_microsecond_form(self):
        stamp = safe_write._pre_restore_stamp()
        self.assertTrue(safe_write.STAMP_RE.match(stamp), stamp)
        self.assertIn(".", stamp.rpartition("-")[0])

    def test_same_second_mixed_forms_order_legacy_first(self):
        eng = self.root / "cfg" / "backups" / "engineering"
        eng.mkdir(parents=True)
        names = [
            "20260101T000000.500000Z-7",
            "20260101T000000Z-9",
            "20260101T000000.000001Z-3",
            "20251231T235959.999999Z-9",
        ]
        for n in names:
            (eng / n).mkdir()
        self.assertEqual(
            safe_write._list_stamps(str(eng)),
            [
                "20251231T235959.999999Z-9",
                "20260101T000000Z-9",
                "20260101T000000.000001Z-3",
                "20260101T000000.500000Z-7",
            ],
        )

    def test_latest_stamp_is_the_microsecond_one_from_the_same_second(self):
        cfg = self.root / "cfg"
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)
        for n in ("20260101T000000Z-9", "20260101T000000.000001Z-3"):
            (eng / n).mkdir()
        self.assertEqual(
            safe_write._resolve_stamp_dir(str(eng), None),
            str(eng / "20260101T000000.000001Z-3"),
        )

    def test_prune_mixed_forms_drops_the_oldest_by_parsed_time(self):
        eng = self.root / "cfg" / "backups" / "engineering"
        eng.mkdir(parents=True)
        names = [
            "20260101T000000Z-9",  # oldest: same second, no fraction
            "20260101T000000.000001Z-9",
            "20260101T000000.000002Z-9",
            "20260101T000000.000003Z-9",
            "20260101T000000.000004Z-9",
            "20260101T000000.000005Z-9",
        ]
        for n in names:
            (eng / n).mkdir()
        safe_write._prune(str(eng))
        remaining = sorted(p.name for p in eng.iterdir())
        self.assertEqual(len(remaining), 5)
        self.assertNotIn("20260101T000000Z-9", remaining)


class MarkWrittenTests(TempDirCase):
    def _manifest(self, cfg, stamp):
        path = cfg / "backups" / "engineering" / stamp / "manifest.json"
        return json.loads(path.read_text())

    @POSIX_ONLY
    def test_mark_written_creates_stamp_dir_and_manifest(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "settings.json").write_bytes(b"{}")
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg), stamp, "2.9.0", "settings.json", "a" * 64, created=True
        )
        manifest = self._manifest(cfg, stamp)
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["installer_version"], "2.9.0")
        self.assertEqual(manifest["stamp"], stamp)
        entry = manifest["files"][0]
        self.assertEqual(entry["rel"], "settings.json")
        self.assertEqual(entry["written_sha256"], "a" * 64)
        self.assertTrue(entry["created"])
        self.assertFalse(entry["removed"])
        self.assertFalse(entry["was_symlink"])
        self.assertIsNone(entry["link_target"])
        self.assertNotIn("stored", entry)
        self.assertEqual(
            stat.S_IMODE(os.stat(cfg / "backups" / "engineering" / stamp).st_mode),
            0o700,
        )

    @SYMLINKS_POSIX_ONLY
    def test_mark_written_created_records_live_symlink(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        real = outside / "policy.md"
        real.write_bytes(b"policy")
        link = cfg / "CLAUDE.md"
        link.symlink_to(real)

        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg), stamp, "2.9.0", "CLAUDE.md", "b" * 64, created=True
        )
        entry = self._manifest(cfg, stamp)["files"][0]
        self.assertTrue(entry["was_symlink"])
        self.assertEqual(entry["link_target"], str(real))

    def test_mark_written_after_backup_keeps_stored_mode_link_target(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        real = outside / "settings.json"
        real.write_bytes(b'{"a":1}')
        link = cfg / "settings.json"
        link.symlink_to(real)

        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(link)])
        before = self._manifest(cfg, stamp)["files"][0]
        safe_write.mark_written(str(cfg), stamp, "2.9.0", "settings.json", "c" * 64)
        entry = self._manifest(cfg, stamp)["files"][0]

        self.assertEqual(entry["stored"], before["stored"])
        self.assertEqual(entry["sha256"], before["sha256"])
        self.assertEqual(entry["mode"], before["mode"])
        self.assertEqual(entry["link_target"], before["link_target"])
        self.assertTrue(entry["was_symlink"])
        self.assertEqual(entry["written_sha256"], "c" * 64)
        self.assertEqual(len(self._manifest(cfg, stamp)["files"]), 1)

    def test_backup_after_mark_written_keeps_written_sha256(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b"new")
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg), stamp, "2.9.0", "settings.json", "d" * 64, created=True
        )
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        entry = self._manifest(cfg, stamp)["files"][0]
        self.assertEqual(entry["written_sha256"], "d" * 64)
        self.assertTrue(entry["created"])
        self.assertEqual(entry["sha256"], safe_write.hashlib.sha256(b"new").hexdigest())
        self.assertIn("stored", entry)

    def test_mark_written_prunes_to_five_stamps(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "settings.json").write_bytes(b"x")
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)
        for i in range(5):
            (eng / "2026010{}T000000Z-1".format(i + 1)).mkdir()
        safe_write.mark_written(
            str(cfg), "20260201T000000.000001Z-1", "2.9.0", "settings.json", "e" * 64
        )
        remaining = sorted(p.name for p in eng.iterdir() if p.is_dir())
        self.assertEqual(len(remaining), 5)
        self.assertNotIn("20260101T000000Z-1", remaining)
        self.assertIn("20260201T000000.000001Z-1", remaining)

    def test_list_written_predicate_exit_codes(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.main(
                ["list", "--cfg", str(cfg), "--stamp", stamp, "--written"]
            )
        self.assertEqual(rc, 1)
        self.assertEqual(captured, [])

        safe_write.mark_written(str(cfg), stamp, "2.9.0", "settings.json", "f" * 64)
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.main(
                ["list", "--cfg", str(cfg), "--stamp", stamp, "--written"]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(captured, [])

        # an unknown stamp is "nothing written", not an error
        self.assertEqual(
            safe_write.main(
                ["list", "--cfg", str(cfg), "--stamp", "20260101T000000Z-2", "--written"]
            ),
            1,
        )

    def test_mark_written_protects_its_own_stamp_from_future_dated_stamps(self):
        # Five pre-existing stamps that sort *after* this run's stamp (e.g. a clock
        # skew or a manually copied backup) must not cause _prune to remove the
        # stamp this run is writing to on its very first mark-written.
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "settings.json").write_bytes(b"x")
        eng = cfg / "backups" / "engineering"
        eng.mkdir(parents=True)
        for i in range(5):
            stamp_dir = eng / "20990101T00000{}Z-1".format(i)
            stamp_dir.mkdir()
            (stamp_dir / "manifest.json").write_text(
                json.dumps({"schema": 1, "installer_version": "x", "files": []})
            )
        run_stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg), run_stamp, "2.9.0", "settings.json", "a" * 64
        )
        self.assertTrue((eng / run_stamp).is_dir(), sorted(p.name for p in eng.iterdir()))

    def test_default_list_output_unchanged(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        safe_write.mark_written(str(cfg), stamp, "2.9.0", "settings.json", "f" * 64)
        self.assertEqual(
            safe_write.list_backups(str(cfg)),
            ["{}\t2.9.0\tsettings.json".format(stamp)],
        )


class OutsideCfgDisclosureTests(TempDirCase):
    def _cfg_with_outside_symlink(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside = self.root / "dotfiles"
        outside.mkdir()
        real = outside / "settings.json"
        real.write_bytes(b'{"a":1}')
        link = cfg / "settings.json"
        link.symlink_to(real)
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(link)])
        real.write_bytes(b'{"a":2}')
        return cfg, real, stamp

    @SYMLINKS_POSIX_ONLY
    def test_disclosure_line_precedes_every_write(self):
        cfg, real, stamp = self._cfg_with_outside_symlink()
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(real.read_bytes(), b'{"a":1}')
        disclosure = "outside config dir: settings.json -> {}".format(os.path.realpath(real))
        self.assertIn(disclosure, captured)
        self.assertEqual(captured.index(disclosure), 0)
        self.assertTrue(captured[1].startswith("pre-restore backup: "), captured)
        self.assertIn("restored settings.json", captured)

    def test_no_outside_cfg_refuses_that_entry_with_exit_8(self):
        cfg, real, stamp = self._cfg_with_outside_symlink()
        # a second, ordinary in-$CFG entry is still restored
        other = cfg / "rules" / "engineering-policy.md"
        other.parent.mkdir()
        other.write_bytes(b"policy")
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(other)])
        other.write_bytes(b"edited")

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, no_outside_cfg=True)
        self.assertEqual(rc, 8)
        self.assertEqual(real.read_bytes(), b'{"a":2}')  # untouched
        self.assertEqual(other.read_bytes(), b"policy")  # restored
        self.assertIn("refused settings.json: outside config dir", captured)
        self.assertIn(
            "outside config dir: settings.json -> {}".format(os.path.realpath(real)), captured
        )

    def test_no_outside_cfg_keeps_the_refused_entry_out_of_pre_restore_backup(self):
        cfg, real, stamp = self._cfg_with_outside_symlink()
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, no_outside_cfg=True)
        self.assertEqual(rc, 8)
        self.assertEqual([l for l in captured if l.startswith("pre-restore backup")], [])


class SymlinkedParentDirRestoreTests(TempDirCase):
    def _cfg_with_symlinked_rules_dir(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside_dir = self.root / "dotfiles-rules"
        outside_dir.mkdir()
        (cfg / "rules").symlink_to(outside_dir)
        x = cfg / "rules" / "x"
        x.write_bytes(b"orig")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(x)])
        return cfg, outside_dir, x, stamp

    def test_target_under_symlinked_parent_dir_is_restored_and_disclosed(self):
        # rules/ itself is a symlink to a directory outside $CFG; rules/x is an
        # ordinary file entry (not itself a symlink). Without --no-outside-cfg it
        # is restored (over the existing path) and disclosed, matching install.sh's
        # documented behaviour.
        cfg, outside_dir, x, stamp = self._cfg_with_symlinked_rules_dir()
        x.write_bytes(b"modified")

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(x.read_bytes(), b"orig")
        self.assertTrue(
            any(l.startswith("outside config dir: rules/x -> ") for l in captured),
            captured,
        )
        self.assertIn("restored rules/x", captured)

    def test_target_under_symlinked_parent_dir_refused_when_missing(self):
        # A restore is never allowed to create a new path outside $CFG, even one
        # that would land under a directory the user's own layout symlinks there.
        cfg, outside_dir, x, stamp = self._cfg_with_symlinked_rules_dir()
        x.unlink()

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 8)
        self.assertFalse(x.exists())
        self.assertIn("refused rules/x: restore target escapes $CFG", captured)


class DanglingOutsideSymlinkRestoreTests(TempDirCase):
    @SYMLINKS_POSIX_ONLY
    def test_dangling_symlink_target_outside_cfg_is_refused_not_created(self):
        # The symlink entry itself is intact, but the file it points to outside
        # $CFG is gone (dangling). Restore must not create it (or any missing
        # parent directories) outside $CFG.
        cfg = self.root / "cfg"
        cfg.mkdir()
        outside_dir = self.root / "outside"
        outside_dir.mkdir()
        real_target = outside_dir / "CLAUDE.md"
        real_target.write_bytes(b"policy content")
        link = cfg / "CLAUDE.md"
        link.symlink_to(real_target)

        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(link)])

        real_target.unlink()
        self.assertTrue(link.is_symlink())
        self.assertFalse(link.exists())

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 8)
        self.assertFalse(real_target.exists())
        self.assertTrue(
            any("outside $CFG is missing; not created" in l for l in captured),
            captured,
        )

    @SYMLINKS_POSIX_ONLY
    def test_dangling_symlink_target_inside_cfg_still_created(self):
        # The existing (pre-fix) behaviour for a dangling symlink whose recorded
        # target is inside $CFG is unchanged: it is fine to create it there.
        cfg = self.root / "cfg"
        cfg.mkdir()
        real_target = cfg / "sub" / "CLAUDE.md"
        real_target.parent.mkdir()
        real_target.write_bytes(b"policy content")
        link = cfg / "CLAUDE.md"
        link.symlink_to(real_target)

        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(link)])

        real_target.unlink()
        real_target.parent.rmdir()
        self.assertTrue(link.is_symlink())
        self.assertFalse(link.exists())

        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(real_target.read_bytes(), b"policy content")


class OnlyRunFilesTests(TempDirCase):
    def _cfg(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        return cfg

    def test_exit_12_when_nothing_is_marked(self):
        cfg = self._cfg()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        with self.assertRaises(safe_write.SafeWriteError) as ctx:
            safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(ctx.exception.code, 12)

    def test_backed_up_entry_restored_when_unchanged_since_the_write(self):
        cfg = self._cfg()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        settings.write_bytes(b"new")
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "settings.json",
            safe_write.hashlib.sha256(b"new").hexdigest(),
        )
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b"old")
        self.assertIn("restored settings.json", captured)
        self.assertEqual(len([l for l in captured if l.startswith("pre-restore")]), 1)

    def test_backed_up_entry_changed_after_the_write_is_reported_not_reverted(self):
        cfg = self._cfg()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        settings.write_bytes(b"new")
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "settings.json",
            safe_write.hashlib.sha256(b"new").hexdigest(),
        )
        settings.write_bytes(b"changed by someone else")
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b"changed by someone else")
        self.assertIn(
            "not rolled back: settings.json changed after this run wrote it", captured
        )

    def test_created_entry_deleted_when_unchanged(self):
        cfg = self._cfg()
        rules = cfg / "rules"
        rules.mkdir()
        policy = rules / "engineering-policy.md"
        policy.write_bytes(b"policy")
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "rules/engineering-policy.md",
            safe_write.hashlib.sha256(b"policy").hexdigest(),
            created=True,
        )
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertFalse(policy.exists())
        self.assertIn("deleted rules/engineering-policy.md", captured)
        self.assertTrue(rules.is_dir())  # the directory stays

    def test_created_entry_changed_after_the_write_is_kept(self):
        cfg = self._cfg()
        marker = cfg / "engineering-installer.json"
        marker.write_bytes(b"{}")
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "engineering-installer.json",
            safe_write.hashlib.sha256(b"{}").hexdigest(),
            created=True,
        )
        marker.write_bytes(b'{"edited": true}')
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertTrue(marker.exists())
        self.assertIn(
            "not rolled back: engineering-installer.json changed after this run "
            "wrote it",
            captured,
        )

    @SYMLINKS_POSIX_ONLY
    def test_created_symlink_entry_unlinks_the_link_not_the_target(self):
        cfg = self._cfg()
        outside = self.root / "dotfiles"
        outside.mkdir()
        real = outside / "policy.md"
        real.write_bytes(b"policy")
        link = cfg / "CLAUDE.md"
        link.symlink_to(real)
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "CLAUDE.md",
            safe_write.hashlib.sha256(b"policy").hexdigest(),
            created=True,
        )
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertFalse(link.is_symlink())
        self.assertTrue(real.exists())
        self.assertEqual(real.read_bytes(), b"policy")
        self.assertIn("deleted CLAUDE.md", captured)
        self.assertIn(
            "outside config dir: CLAUDE.md -> {}".format(os.path.realpath(real)), captured
        )

    def test_created_entry_now_pointing_elsewhere_outside_cfg_is_refused(self):
        cfg = self._cfg()
        outside = self.root / "dotfiles"
        outside.mkdir()
        recorded = outside / "policy.md"
        recorded.write_bytes(b"policy")
        other = outside / "other.md"
        other.write_bytes(b"policy")  # same bytes, different file
        link = cfg / "CLAUDE.md"
        link.symlink_to(recorded)
        stamp = "20260101T000000.000001Z-1"
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "CLAUDE.md",
            safe_write.hashlib.sha256(b"policy").hexdigest(),
            created=True,
        )
        link.unlink()
        link.symlink_to(other)

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 8)
        self.assertTrue(link.is_symlink())
        self.assertTrue(other.exists())
        self.assertIn("refused CLAUDE.md: delete target escapes $CFG", captured)

    def test_removed_entry_restored_only_when_absent(self):
        cfg = self._cfg()
        claude = cfg / "CLAUDE.md"
        claude.write_bytes(b"legacy policy")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(claude)])
        pre_sha = safe_write.hashlib.sha256(b"legacy policy").hexdigest()
        claude.unlink()
        safe_write.mark_written(
            str(cfg), stamp, "2.9.0", "CLAUDE.md", pre_sha, removed=True
        )

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertEqual(claude.read_bytes(), b"legacy policy")
        self.assertIn("restored CLAUDE.md", captured)

        # someone recreated the path since: leave it alone
        claude.write_bytes(b"a new file the user made")
        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertEqual(claude.read_bytes(), b"a new file the user made")
        self.assertIn(
            "not rolled back: CLAUDE.md changed after this run wrote it", captured
        )

    def test_unmarked_entries_are_ignored(self):
        cfg = self._cfg()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        other = cfg / "other.json"
        other.write_bytes(b"other-old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings), str(other)])
        settings.write_bytes(b"new")
        other.write_bytes(b"other-new")
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "settings.json",
            safe_write.hashlib.sha256(b"new").hexdigest(),
        )
        rc = safe_write.restore(str(cfg), stamp=stamp, only_run_files=True)
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b"old")
        self.assertEqual(other.read_bytes(), b"other-new")


class PlainRestoreWithMarkedEntriesTests(TempDirCase):
    def test_plain_restore_skips_created_entries_and_exits_0(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        settings = cfg / "settings.json"
        settings.write_bytes(b"old")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(settings)])
        settings.write_bytes(b"new")
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "settings.json",
            safe_write.hashlib.sha256(b"new").hexdigest(),
        )
        marker = cfg / "engineering-installer.json"
        marker.write_bytes(b"{}")
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "engineering-installer.json",
            safe_write.hashlib.sha256(b"{}").hexdigest(),
            created=True,
        )

        captured = []
        with mock.patch("builtins.print", side_effect=lambda *a: captured.append(a[0])):
            rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(settings.read_bytes(), b"old")
        self.assertTrue(marker.exists())
        self.assertEqual(
            [l for l in captured if "engineering-installer.json" in l], []
        )

    def test_plain_restore_puts_a_removed_entry_back(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        claude = cfg / "CLAUDE.md"
        claude.write_bytes(b"legacy policy")
        stamp = "20260101T000000.000001Z-1"
        safe_write.backup(str(cfg), stamp, "2.9.0", [str(claude)])
        claude.unlink()
        safe_write.mark_written(
            str(cfg),
            stamp,
            "2.9.0",
            "CLAUDE.md",
            safe_write.hashlib.sha256(b"legacy policy").hexdigest(),
            removed=True,
        )
        rc = safe_write.restore(str(cfg), stamp=stamp)
        self.assertEqual(rc, 0)
        self.assertEqual(claude.read_bytes(), b"legacy policy")


class CliTests(TempDirCase):
    def test_write_via_cli_stdin(self):
        target = self.root / "f.json"
        src = self.root / "src.txt"
        src.write_bytes(b"hello")
        rc = safe_write.main(
            [
                "write",
                "--target",
                str(target),
                "--from",
                str(src),
                "--default-mode",
                "0600",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(target.read_bytes(), b"hello")

    @POSIX_ONLY
    def test_write_creates_missing_cfg_as_0700_and_parents_0755(self):
        cfg = self.root / "cfg"
        target = cfg / "rules" / "engineering-policy.md"
        src = self.root / "src.txt"
        src.write_bytes(b"policy")
        rc = safe_write.main(
            [
                "write",
                "--target",
                str(target),
                "--from",
                str(src),
                "--default-mode",
                "0644",
                "--cfg",
                str(cfg),
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(target.read_bytes(), b"policy")
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((cfg / "rules").stat().st_mode), 0o755)

    @POSIX_ONLY
    def test_write_cfg_directly_in_cfg_dir(self):
        cfg = self.root / "cfg"
        target = cfg / "settings.json"
        src = self.root / "src.txt"
        src.write_bytes(b"{}")
        rc = safe_write.main(
            [
                "write",
                "--target",
                str(target),
                "--from",
                str(src),
                "--default-mode",
                "0600",
                "--cfg",
                str(cfg),
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    @POSIX_ONLY
    def test_write_without_cfg_keeps_existing_cfg_mode(self):
        cfg = self.root / "cfg"
        cfg.mkdir(mode=0o755)
        target = cfg / "settings.json"
        src = self.root / "src.txt"
        src.write_bytes(b"{}")
        rc = safe_write.main(
            [
                "write",
                "--target",
                str(target),
                "--from",
                str(src),
                "--default-mode",
                "0600",
                "--cfg",
                str(cfg),
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode), 0o755)

    def test_check_cli_exit_codes(self):
        target = self.root / "f.json"
        rc = safe_write.main(["check", "--target", str(target)])
        self.assertEqual(rc, 0)

    def test_mark_written_cli_round_trip(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        (cfg / "settings.json").write_bytes(b"{}")
        stamp = "20260101T000000.000001Z-1"
        rc = safe_write.main(
            [
                "mark-written",
                "--cfg",
                str(cfg),
                "--stamp",
                stamp,
                "--version",
                "2.9.0",
                "--rel",
                "settings.json",
                "--written-sha",
                "a" * 64,
                "--created",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(
            safe_write.main(["list", "--cfg", str(cfg), "--stamp", stamp, "--written"]),
            0,
        )

    def test_list_cli_empty(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        rc = safe_write.main(["list", "--cfg", str(cfg)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
