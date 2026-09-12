from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import merge_settings as ms  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "merge_settings.py"
RECOMMENDED_FIXTURE = REPO_ROOT / "settings.recommended.json"


def run_cli(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        text=True,
        encoding="utf-8",  # the CLI writes UTF-8 regardless of the console code page
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
        cwd=cwd,
    )


def write(path: Path, content: str, encoding="utf-8"):
    path.write_text(content, encoding=encoding)
    return path


class LoadCurrentTests(unittest.TestCase):
    def test_missing_file_is_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "settings.json"
            self.assertEqual(ms.load_current(str(missing)), {})

    def test_empty_file_is_empty_dict_with_note(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", "")
            self.assertEqual(ms.load_current(str(p)), {})

    def test_whitespace_only_file_is_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", "   \n\t  \n")
            self.assertEqual(ms.load_current(str(p)), {})

    def test_bom_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "settings.json"
            p.write_bytes(b"\xef\xbb\xbf" + b'{"model": "opus"}')
            self.assertEqual(ms.load_current(str(p)), {"model": "opus"})

    def test_non_utf8_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "settings.json"
            p.write_bytes(b"\xff\xfe\x00\x01")
            with self.assertRaises(ms.UnusableSettings) as ctx:
                ms.load_current(str(p))
            self.assertIn("not UTF-8", str(ctx.exception))

    def test_invalid_json_message_has_line_column_and_rule(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", '{\n  "a": 1,\n}\n')
            with self.assertRaises(ms.UnusableSettings) as ctx:
                ms.load_current(str(p))
            msg = str(ctx.exception)
            self.assertIn("line", msg)
            self.assertIn("column", msg)
            self.assertIn("comments and trailing commas are not allowed", msg)

    def test_null_top_level_raises_typed_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", "null")
            with self.assertRaises(ms.UnusableSettings) as ctx:
                ms.load_current(str(p))
            self.assertIn("top level is null, expected an object", str(ctx.exception))

    def test_array_top_level_raises_typed_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", "[]")
            with self.assertRaises(ms.UnusableSettings) as ctx:
                ms.load_current(str(p))
            self.assertIn("top level is array, expected an object", str(ctx.exception))

    def test_scalar_top_level_raises_typed_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = write(Path(td) / "settings.json", '"x"')
            with self.assertRaises(ms.UnusableSettings) as ctx:
                ms.load_current(str(p))
            self.assertIn("top level is string, expected an object", str(ctx.exception))

            p2 = write(Path(td) / "settings2.json", "42")
            with self.assertRaises(ms.UnusableSettings) as ctx2:
                ms.load_current(str(p2))
            self.assertIn("top level is number, expected an object", str(ctx2.exception))


class MergeRuleTests(unittest.TestCase):
    def test_nested_dict_recursion_env(self):
        current = {"env": {"FOO": "1"}}
        recommended = {"env": {"BAR": "2"}}
        merged, _ = ms.merge(current, recommended, "enforce")
        self.assertEqual(merged["env"], {"FOO": "1", "BAR": "2"})

    def test_list_union_order_and_dedup(self):
        current = {"permissions": {"allow": ["b", "a"]}}
        recommended = {"permissions": {"allow": ["a", "c"]}}
        merged, _ = ms.merge(current, recommended, "enforce")
        self.assertEqual(merged["permissions"]["allow"], ["b", "a", "c"])

    def test_list_union_of_dict_entries_dedup(self):
        current = {"x": [{"a": 1, "b": 2}]}
        recommended = {"x": [{"b": 2, "a": 1}, {"c": 3}]}
        merged, _ = ms.merge(current, recommended, "enforce")
        self.assertEqual(merged["x"], [{"a": 1, "b": 2}, {"c": 3}])

    def test_marketplace_replace_whole_by_name_enforce_drops_stale_subkey(self):
        current = {
            "extraKnownMarketplaces": {
                "engineering": {"source": {"source": "github", "repo": "old/repo", "ref": "v1"}}
            }
        }
        recommended = {
            "extraKnownMarketplaces": {
                "engineering": {"source": {"source": "github", "repo": "new/repo"}}
            }
        }
        merged, drift = ms.merge(current, recommended, "enforce")
        self.assertEqual(
            merged["extraKnownMarketplaces"]["engineering"],
            {"source": {"source": "github", "repo": "new/repo"}},
        )
        self.assertTrue(any("extraKnownMarketplaces.engineering" in d for d in drift))

    def test_marketplace_replace_whole_by_name_defaults_keeps_entry(self):
        current = {
            "extraKnownMarketplaces": {
                "engineering": {"source": {"source": "github", "repo": "old/repo", "ref": "v1"}}
            }
        }
        recommended = {
            "extraKnownMarketplaces": {
                "engineering": {"source": {"source": "github", "repo": "new/repo"}}
            }
        }
        merged, _ = ms.merge(current, recommended, "defaults")
        self.assertEqual(
            merged["extraKnownMarketplaces"]["engineering"],
            {"source": {"source": "github", "repo": "old/repo", "ref": "v1"}},
        )

    def test_replace_whole_keys_enforce_and_defaults(self):
        for key in ("fallbackModel", "modelPicker", "availableModels"):
            current = {key: {"x": 1}}
            recommended = {key: {"y": 2}}
            merged_enforce, _ = ms.merge(current, recommended, "enforce")
            self.assertEqual(merged_enforce[key], {"y": 2})
            merged_defaults, _ = ms.merge(current, recommended, "defaults")
            self.assertEqual(merged_defaults[key], {"x": 1})

    def test_official_plugin_explicit_false_preserved(self):
        current = {"enabledPlugins": {"superpowers@claude-plugins-official": False}}
        recommended = {"enabledPlugins": {"superpowers@claude-plugins-official": True}}
        for mode in ("enforce", "defaults"):
            merged, _ = ms.merge(current, recommended, mode)
            self.assertFalse(merged["enabledPlugins"]["superpowers@claude-plugins-official"])

    def test_engineering_plugin_forced_true_from_false(self):
        current = {"enabledPlugins": {"engineering@engineering": False}}
        recommended = {}
        for mode in ("enforce", "defaults"):
            merged, _ = ms.merge(current, recommended, mode)
            self.assertTrue(merged["enabledPlugins"]["engineering@engineering"])

    def test_engineering_plugin_forced_true_when_absent_entirely(self):
        merged, _ = ms.merge({}, {}, "enforce")
        self.assertTrue(merged["enabledPlugins"]["engineering@engineering"])

    def test_key_order_schema_first_then_current_then_new(self):
        current = {"b": 1, "a": 2}
        recommended = {"c": 3, "a": 99, "d": 4}
        merged, _ = ms.merge(current, recommended, "defaults")
        self.assertEqual(list(merged.keys()), ["$schema", "b", "a", "c", "d", "enabledPlugins"])

    def test_schema_kept_if_present_never_overwritten(self):
        current = {"$schema": "https://example.invalid/custom.json"}
        merged, _ = ms.merge(current, {}, "enforce")
        self.assertEqual(merged["$schema"], "https://example.invalid/custom.json")

    def test_schema_inserted_first_when_absent(self):
        merged, _ = ms.merge({}, {}, "enforce")
        self.assertEqual(next(iter(merged.keys())), "$schema")
        self.assertEqual(merged["$schema"], ms.SCHEMA_URL)

    def test_scalar_enforce_recommended_wins(self):
        merged, _ = ms.merge({"model": "opus"}, {"model": "sonnet"}, "enforce")
        self.assertEqual(merged["model"], "sonnet")

    def test_scalar_defaults_current_wins(self):
        merged, _ = ms.merge({"model": "opus"}, {"model": "sonnet"}, "defaults")
        self.assertEqual(merged["model"], "opus")

    def test_scalar_defaults_fills_absent(self):
        merged, _ = ms.merge({}, {"model": "sonnet"}, "defaults")
        self.assertEqual(merged["model"], "sonnet")

    def test_current_only_key_kept_both_modes(self):
        for mode in ("enforce", "defaults"):
            merged, _ = ms.merge({"onlyCurrent": 1}, {}, mode)
            self.assertEqual(merged["onlyCurrent"], 1)

    def test_idempotence_enforce(self):
        current = {"model": "opus", "env": {"FOO": "1"}}
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        merged1, _ = ms.merge(current, recommended, "enforce")
        merged2, _ = ms.merge(merged1, recommended, "enforce")
        self.assertEqual(merged1, merged2)

    def test_idempotence_defaults(self):
        current = {"model": "opus", "env": {"FOO": "1"}}
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        merged1, _ = ms.merge(current, recommended, "defaults")
        merged2, _ = ms.merge(merged1, recommended, "defaults")
        self.assertEqual(merged1, merged2)

    def test_non_ascii_values_preserved_in_merge(self):
        current = {"outputStyle": "简体中文"}
        merged, _ = ms.merge(current, {}, "enforce")
        self.assertEqual(merged["outputStyle"], "简体中文")

    def test_drift_report_content_defaults_mode(self):
        current = {"model": "opus"}
        recommended = {"model": "sonnet"}
        merged, drift = ms.merge(current, recommended, "defaults")
        self.assertEqual(merged["model"], "opus")
        self.assertEqual(len(drift), 1)
        self.assertIn("model: recommended=", drift[0])
        self.assertIn("current=", drift[0])

    def test_no_official_leaves_existing_official_entries_alone(self):
        current = {
            "enabledPlugins": {"superpowers@claude-plugins-official": True},
            "extraKnownMarketplaces": {
                "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/x"}}
            },
        }
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        merged, _ = ms.merge(current, recommended, "enforce", no_official=True)
        self.assertTrue(merged["enabledPlugins"]["superpowers@claude-plugins-official"])
        self.assertIn("claude-plugins-official", merged["extraKnownMarketplaces"])
        for k in merged["enabledPlugins"]:
            if k not in ("superpowers@claude-plugins-official", "engineering@engineering"):
                self.fail("no-official should not add new official entries: %s" % k)

    def test_purge_official_removes_true_keeps_false_and_removes_marketplace(self):
        current = {
            "enabledPlugins": {
                "superpowers@claude-plugins-official": True,
                "context7@claude-plugins-official": False,
            },
            "extraKnownMarketplaces": {
                "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/x"}}
            },
        }
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        merged, _ = ms.merge(current, recommended, "enforce", purge_official=True)
        self.assertNotIn("superpowers@claude-plugins-official", merged["enabledPlugins"])
        self.assertIn("context7@claude-plugins-official", merged["enabledPlugins"])
        self.assertFalse(merged["enabledPlugins"]["context7@claude-plugins-official"])
        self.assertNotIn("claude-plugins-official", merged["extraKnownMarketplaces"])

    def test_purge_official_removes_non_false_values_of_any_type(self):
        current = {
            "enabledPlugins": {
                "string@claude-plugins-official": "yes",
                "null@claude-plugins-official": None,
                "object@claude-plugins-official": {"x": 1},
                "true@claude-plugins-official": True,
                "false@claude-plugins-official": False,
            },
        }
        recommended = {}
        merged, _ = ms.merge(current, recommended, "enforce", purge_official=True)
        remaining = merged["enabledPlugins"]
        self.assertEqual(
            {k for k in remaining if k.endswith(ms.OFFICIAL_SUFFIX)},
            {"false@claude-plugins-official"},
        )
        self.assertFalse(remaining["false@claude-plugins-official"])

    def test_drift_report_defaults_mode_includes_enabled_plugin_user_disabled(self):
        current = {"enabledPlugins": {"context7@claude-plugins-official": False}}
        recommended = {"enabledPlugins": {"context7@claude-plugins-official": True}}
        merged, drift = ms.merge(current, recommended, "defaults")
        self.assertFalse(merged["enabledPlugins"]["context7@claude-plugins-official"])
        self.assertTrue(
            any(d.startswith("enabledPlugins.context7@claude-plugins-official: ") for d in drift),
            drift,
        )

    def test_alias_only_difference_produces_no_drift_and_keeps_user_spelling(self):
        current = {"model": "opus[1m]"}
        recommended = {"model": "opus"}
        for mode in ("enforce", "defaults"):
            merged, drift = ms.merge(current, recommended, mode)
            self.assertEqual(merged["model"], "opus[1m]")
            self.assertEqual(drift, [])

    def test_alias_only_difference_fallback_model_no_drift(self):
        current = {"fallbackModel": ["opus[1m]", "sonnet"]}
        recommended = {"fallbackModel": ["opus", "sonnet"]}
        merged, drift = ms.merge(current, recommended, "enforce")
        self.assertEqual(merged["fallbackModel"], ["opus[1m]", "sonnet"])
        self.assertEqual(drift, [])

    def test_real_model_difference_still_drifts_and_enforces(self):
        merged, drift = ms.merge({"model": "opus"}, {"model": "sonnet"}, "enforce")
        self.assertEqual(merged["model"], "sonnet")
        self.assertTrue(any(d.startswith("model: ") for d in drift))

    def test_redact_env_values_in_drift_report(self):
        current = {"env": {"API_KEY": "sk-secret-value"}}
        recommended = {"env": {"API_KEY": "sk-other-value"}}
        merged, drift = ms.merge(current, recommended, "defaults")
        self.assertEqual(merged["env"]["API_KEY"], "sk-secret-value")
        self.assertEqual(len(drift), 1)
        self.assertNotIn("sk-secret-value", drift[0])
        self.assertNotIn("sk-other-value", drift[0])
        self.assertIn("<redacted>", drift[0])

    def test_redact_secret_key_pattern_in_drift_report(self):
        current = {"apiToken": "abc123"}
        recommended = {"apiToken": "xyz789"}
        merged, drift = ms.merge(current, recommended, "defaults")
        self.assertEqual(len(drift), 1)
        self.assertNotIn("abc123", drift[0])
        self.assertNotIn("xyz789", drift[0])
        self.assertIn("<redacted>", drift[0])

    def test_redact_api_key_helper_in_drift_report(self):
        current = {"apiKeyHelper": "old-helper"}
        recommended = {"apiKeyHelper": "new-helper"}
        merged, drift = ms.merge(current, recommended, "defaults")
        self.assertEqual(len(drift), 1)
        self.assertNotIn("old-helper", drift[0])
        self.assertNotIn("new-helper", drift[0])
        self.assertIn("<redacted>", drift[0])

    def test_no_redact_false_shows_real_values_in_drift_report(self):
        current = {"env": {"API_KEY": "sk-secret-value"}}
        recommended = {"env": {"API_KEY": "sk-other-value"}}
        merged, drift = ms.merge(current, recommended, "defaults", redact=False)
        self.assertEqual(len(drift), 1)
        self.assertIn("sk-secret-value", drift[0])
        self.assertIn("sk-other-value", drift[0])


class SameTests(unittest.TestCase):
    def test_same_equal_dicts(self):
        self.assertTrue(ms.same({"a": 1}, {"a": 1}))

    def test_same_differing_dicts(self):
        self.assertFalse(ms.same({"a": 1}, {"a": 2}))

    def test_same_canonicalises_model_alias(self):
        self.assertTrue(ms.same({"model": "opus[1m]"}, {"model": "opus"}))

    def test_same_canonicalises_model_settings_keys(self):
        a = {"modelSettings": {"opus[1m]": {"effortLevel": "low"}}}
        b = {"modelSettings": {"opus": {"effortLevel": "low"}}}
        self.assertTrue(ms.same(a, b))

    def test_same_canonicalises_fallback_model_list(self):
        a = {"fallbackModel": ["opus[1m]", "sonnet"]}
        b = {"fallbackModel": ["opus", "sonnet"]}
        self.assertTrue(ms.same(a, b))


class CliTests(unittest.TestCase):
    def test_check_exit_0_when_equal(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(
                Path(td) / "current.json",
                json.dumps({"$schema": ms.SCHEMA_URL, "enabledPlugins": {"engineering@engineering": True}}),
            )
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--check"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_check_exit_10_when_differs(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"model": "opus"}))
            recommended = write(Path(td) / "recommended.json", json.dumps({"model": "sonnet"}))
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--check"]
            )
            self.assertEqual(proc.returncode, 10)
            self.assertEqual(proc.stdout, "")

    def test_check_exit_0_for_alias_only_difference(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(
                Path(td) / "current.json",
                json.dumps({"$schema": ms.SCHEMA_URL, "model": "opus", "enabledPlugins": {"engineering@engineering": True}}),
            )
            recommended = write(Path(td) / "recommended.json", json.dumps({"model": "opus[1m]"}))
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--check"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_invalid_json_exits_3(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", "{bad json")
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(["--current", str(current), "--recommended", str(recommended), "--mode", "enforce"])
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(proc.stdout, "")

    def test_missing_required_arg_exits_2(self):
        proc = run_cli(["--current", "x.json", "--mode", "enforce"])
        self.assertEqual(proc.returncode, 2)

    def test_invalid_mode_exits_2(self):
        proc = run_cli(["--current", "x.json", "--recommended", "y.json", "--mode", "bogus"])
        self.assertEqual(proc.returncode, 2)

    def test_stdout_key_order_and_trailing_newline(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"b": 1, "a": 2}))
            recommended = write(Path(td) / "recommended.json", json.dumps({"c": 3}))
            proc = run_cli(["--current", str(current), "--recommended", str(recommended), "--mode", "defaults"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(proc.stdout.endswith("\n"))
            merged = json.loads(proc.stdout)
            self.assertEqual(list(merged.keys())[0], "$schema")

    def test_drift_report_printed_to_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"model": "opus"}))
            recommended = write(Path(td) / "recommended.json", json.dumps({"model": "sonnet"}))
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "defaults", "--drift-report"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("drift: model: recommended=", proc.stderr)

    def test_diff_output_nonempty_when_changed(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"model": "opus"}))
            recommended = write(Path(td) / "recommended.json", json.dumps({"model": "sonnet"}))
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--diff"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotEqual(proc.stdout, "")

    def test_diff_output_empty_when_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            already_merged = {
                "$schema": ms.SCHEMA_URL,
                "enabledPlugins": {"engineering@engineering": True},
            }
            current = write(Path(td) / "current.json", json.dumps(already_merged))
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--diff"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_diff_redacts_secret_values_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(
                Path(td) / "current.json", json.dumps({"env": {"API_KEY": "sk-secret-value"}})
            )
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(
                ["--current", str(current), "--recommended", str(recommended), "--mode", "enforce", "--diff"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("sk-secret-value", proc.stdout)

    def test_diff_shows_real_values_with_no_redact(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(
                Path(td) / "current.json", json.dumps({"env": {"API_KEY": "sk-secret-value"}})
            )
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(
                [
                    "--current", str(current), "--recommended", str(recommended),
                    "--mode", "enforce", "--diff", "--no-redact",
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("sk-secret-value", proc.stdout)

    def test_drift_report_redacts_secret_values_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"env": {"API_KEY": "sk-secret-value"}}))
            recommended = write(Path(td) / "recommended.json", json.dumps({"env": {"API_KEY": "sk-other-value"}}))
            proc = run_cli(
                [
                    "--current", str(current), "--recommended", str(recommended),
                    "--mode", "defaults", "--drift-report",
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("sk-secret-value", proc.stderr)
            self.assertNotIn("sk-other-value", proc.stderr)
            self.assertIn("<redacted>", proc.stderr)

    def test_plain_merged_output_not_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(Path(td) / "current.json", json.dumps({"env": {"API_KEY": "sk-secret-value"}}))
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(["--current", str(current), "--recommended", str(recommended), "--mode", "enforce"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("sk-secret-value", proc.stdout)

    def test_non_ascii_round_trip_cli(self):
        with tempfile.TemporaryDirectory() as td:
            current = write(
                Path(td) / "current.json",
                json.dumps({"outputStyle": "简体中文"}, ensure_ascii=False),
                encoding="utf-8",
            )
            recommended = write(Path(td) / "recommended.json", "{}")
            proc = run_cli(["--current", str(current), "--recommended", str(recommended), "--mode", "enforce"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("简体中文", proc.stdout)
            self.assertNotIn("\\u", proc.stdout)


class RecommendedFixtureTests(unittest.TestCase):
    def test_recommended_model_is_normalised_form(self):
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(recommended.get("model"), "fable[1m]")

    def test_recommended_lists_are_unioned_if_any_exist(self):
        recommended = json.loads(RECOMMENDED_FIXTURE.read_text(encoding="utf-8"))
        list_keys = [k for k, v in recommended.items() if isinstance(v, list)]
        for key in list_keys:
            current = {key: ["__current_only_marker__"] + list(recommended[key])}
            merged, _ = ms.merge(current, recommended, "enforce")
            self.assertIn("__current_only_marker__", merged[key])
            for item in recommended[key]:
                self.assertIn(item, merged[key])
        # This assertion always runs so a future list added to the
        # recommendation is exercised by the loop above automatically.
        self.assertIsInstance(list_keys, list)


if __name__ == "__main__":
    unittest.main()


class NestedRedactionTests(unittest.TestCase):
    def test_nested_env_and_whole_entry_drift_are_redacted(self):
        current = {"managedMcpServers": {"x": {"command": "a", "env": {"GITHUB_PAT": "ghp_s3cret"}}}}
        recommended = {"managedMcpServers": {"x": {"command": "b"}}}
        _, drift = ms.merge(current, recommended, "defaults")
        joined = "\n".join(drift)
        self.assertIn("managedMcpServers.x", joined)
        self.assertNotIn("ghp_s3cret", joined)

    def test_nested_env_redacted_in_settings_copy(self):
        red = ms._redact_settings({"mcpServers": {"y": {"env": {"AUTH": "v"}}}})
        self.assertEqual(red["mcpServers"]["y"]["env"]["AUTH"], ms.REDACTED)

