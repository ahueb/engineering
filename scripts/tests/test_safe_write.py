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

    def test_list_cli_empty(self):
        cfg = self.root / "cfg"
        cfg.mkdir()
        rc = safe_write.main(["list", "--cfg", str(cfg)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
