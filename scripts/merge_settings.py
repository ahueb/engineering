#!/usr/bin/env python3
"""Merge a user's Claude Code settings.json with the repo's recommended
settings, mirroring how Claude Code itself combines settings sources.

Python >= 3.8, stdlib only. See docs/plans/2026-09-12-installer-merge-hardening.md
(decision 3-4) and the Task 1 interface contract for the exact rules.

Importable API:
    load_current(path) -> dict          (raises UnusableSettings)
    merge(current, recommended, mode, no_official=False, purge_official=False,
          redact=True) -> (merged: dict, drift: list[str])
    same(a, b) -> bool
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import re
import sys

SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"
OFFICIAL_SUFFIX = "@claude-plugins-official"
OFFICIAL_MARKETPLACE_NAME = "claude-plugins-official"
ENGINEERING_PLUGIN_KEY = "engineering@engineering"
ALIAS_SUFFIX = "[1m]"
REDACTED = "<redacted>"
_SECRET_KEY_RE = re.compile(r"(key|token|secret|password|credential)", re.IGNORECASE)

# Keys whose value is a dict of name -> entry, where each *entry* replaces
# whole (enforce) or is left untouched if already present (defaults).
REPLACE_WHOLE_BY_NAME = {"extraKnownMarketplaces", "managedMcpServers"}

# Keys whose value is treated as a single atomic unit that replaces whole
# (enforce) or is kept if already present (defaults), never merged into.
REPLACE_WHOLE = {"fallbackModel", "modelPicker", "availableModels"}


class UnusableSettings(Exception):
    """Raised when the current settings file cannot be used as-is."""


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _json_type_name(obj):
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "boolean"
    if isinstance(obj, list):
        return "array"
    if isinstance(obj, str):
        return "string"
    if isinstance(obj, (int, float)):
        return "number"
    return type(obj).__name__


def load_current(path):
    """Load a settings JSON file as a dict.

    Missing file -> {}. Empty / whitespace-only file -> {} plus a stderr
    note. Anything else that cannot be used raises UnusableSettings.
    """
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as exc:
        raise UnusableSettings("%s: cannot be read: %s" % (path, exc))

    if len(raw.strip()) == 0:
        sys.stderr.write("note: %s is empty; treating as {}\n" % path)
        return {}

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UnusableSettings("%s: is not UTF-8" % path)

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UnusableSettings(
            "%s: invalid JSON at line %d column %d: %s "
            "(comments and trailing commas are not allowed)"
            % (path, exc.lineno, exc.colno, exc.msg)
        )

    if not isinstance(obj, dict):
        raise UnusableSettings(
            "%s: top level is %s, expected an object" % (path, _json_type_name(obj))
        )

    return obj


# --------------------------------------------------------------------------
# Merge helpers
# --------------------------------------------------------------------------

def _canon_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _dedup_union(current_list, recommended_list):
    """Union current items (in order) then recommended items not already
    present, deduplicated by structural (canonical JSON) equality."""
    seen = set()
    out = []
    for item in list(current_list) + list(recommended_list):
        key = _canon_json(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _strip_alias(value):
    if isinstance(value, str) and value.endswith(ALIAS_SUFFIX):
        return value[: -len(ALIAS_SUFFIX)]
    return value


def _canonicalize_aliases(obj):
    """Deep-copy obj, stripping the '[1m]' alias suffix from model-alias
    strings at the paths documented in the contract: `model`, entries of
    `fallbackModel`, and the keys of `modelSettings`."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "modelSettings" and isinstance(v, dict):
                result[k] = {
                    _strip_alias(mk): _canonicalize_aliases(mv) for mk, mv in v.items()
                }
                continue
            if k == "model" and isinstance(v, str):
                result[k] = _strip_alias(v)
                continue
            if k == "fallbackModel":
                if isinstance(v, list):
                    result[k] = [
                        _strip_alias(x) if isinstance(x, str) else _canonicalize_aliases(x)
                        for x in v
                    ]
                elif isinstance(v, str):
                    result[k] = _strip_alias(v)
                else:
                    result[k] = _canonicalize_aliases(v)
                continue
            result[k] = _canonicalize_aliases(v)
        return result
    if isinstance(obj, list):
        return [_canonicalize_aliases(x) for x in obj]
    return obj


def same(a, b):
    """Structural equality, canonicalising model-alias strings on both sides."""
    return _canonicalize_aliases(a) == _canonicalize_aliases(b)


def _canon_eq_at(key, a, b):
    """Value equality for two values that both live under dict key `key`,
    after the same alias canonicalisation _canonicalize_aliases()/same()
    applies at that key (e.g. `model`, `fallbackModel`). Used for
    drift/diff/replace decisions so a merely alias-spelled value is never
    treated as a real difference."""
    wrapped = _canonicalize_aliases({key: a})
    wrapped_b = _canonicalize_aliases({key: b})
    return wrapped[key] == wrapped_b[key]


def _merge_enabled_plugins(current, recommended, path_prefix, drift):
    """enabledPlugins: existing user entries (including explicit false) are
    always kept; only missing entries are filled from the recommendation.
    This holds in both modes. engineering@engineering is always forced true.
    Records drift for any key present in both sides whose merged (kept)
    value differs from the recommendation, e.g. a plugin the user disabled
    that the recommendation enables."""
    merged = dict(current) if isinstance(current, dict) else {}
    if isinstance(recommended, dict):
        for k, v in recommended.items():
            sub_path = "%s.%s" % (path_prefix, k) if path_prefix else k
            if k not in merged:
                merged[k] = v
            elif not _canon_eq_at(k, merged[k], v):
                drift.append((sub_path, v, merged[k]))
    merged[ENGINEERING_PLUGIN_KEY] = True
    return merged


def _merge_replace_whole_by_name(current, recommended, mode, path_prefix, drift):
    current = current if isinstance(current, dict) else {}
    recommended = recommended if isinstance(recommended, dict) else {}
    merged = dict(current)
    for name, rec_entry in recommended.items():
        sub_path = "%s.%s" % (path_prefix, name)
        if name in current:
            if not _canon_eq_at(name, current[name], rec_entry):
                drift.append((sub_path, rec_entry, current[name]))
                if mode == "enforce":
                    merged[name] = copy.deepcopy(rec_entry)
                # defaults: leave the existing entry untouched (already in merged)
            # else: canonically equal (e.g. alias spelling only) -> keep user's entry
        else:
            merged[name] = copy.deepcopy(rec_entry)
    return merged


def _merge_value(cur_present, cur_val, rec_present, rec_val, mode, path, drift, key):
    if cur_present and rec_present and isinstance(cur_val, dict) and isinstance(rec_val, dict):
        return _merge_dict(cur_val, rec_val, mode, path, drift)
    if not cur_present and rec_present and isinstance(rec_val, dict):
        return copy.deepcopy(rec_val)
    if cur_present and not rec_present:
        return cur_val

    if cur_present and rec_present and isinstance(cur_val, list) and isinstance(rec_val, list):
        return _dedup_union(cur_val, rec_val)
    if not cur_present and rec_present and isinstance(rec_val, list):
        return copy.deepcopy(rec_val)

    # Everything else replaces.
    if cur_present and rec_present:
        if not _canon_eq_at(key, cur_val, rec_val):
            drift.append((path, rec_val, cur_val))
            return copy.deepcopy(rec_val) if mode == "enforce" else cur_val
        return cur_val
    if rec_present:
        return copy.deepcopy(rec_val)
    return cur_val


def _merge_dict(current, recommended, mode, path_prefix, drift):
    merged = {}
    cur_keys = list(current.keys())
    rec_keys = [k for k in recommended.keys() if k not in current]

    for k in cur_keys + rec_keys:
        sub_path = "%s.%s" % (path_prefix, k) if path_prefix else k
        cur_present = k in current
        rec_present = k in recommended
        cur_val = current.get(k)
        rec_val = recommended.get(k)

        if k == "enabledPlugins":
            merged[k] = _merge_enabled_plugins(
                cur_val if cur_present else {}, rec_val if rec_present else {}, sub_path, drift
            )
            continue

        if k in REPLACE_WHOLE_BY_NAME:
            merged[k] = _merge_replace_whole_by_name(
                cur_val if cur_present else {}, rec_val if rec_present else {}, mode, sub_path, drift
            )
            continue

        if k in REPLACE_WHOLE:
            if cur_present and rec_present:
                if not _canon_eq_at(k, cur_val, rec_val):
                    drift.append((sub_path, rec_val, cur_val))
                    merged[k] = copy.deepcopy(rec_val) if mode == "enforce" else cur_val
                else:
                    merged[k] = cur_val
            elif rec_present:
                merged[k] = copy.deepcopy(rec_val)
            else:
                merged[k] = cur_val
            continue

        merged[k] = _merge_value(cur_present, cur_val, rec_present, rec_val, mode, sub_path, drift, k)

    return merged


def _strip_official(recommended):
    """Remove official-marketplace plugin entries and the official
    marketplace registration from a (copy of a) recommendation dict."""
    rec = copy.deepcopy(recommended)
    enabled = rec.get("enabledPlugins")
    if isinstance(enabled, dict):
        rec["enabledPlugins"] = {
            k: v for k, v in enabled.items() if not k.endswith(OFFICIAL_SUFFIX)
        }
    marketplaces = rec.get("extraKnownMarketplaces")
    if isinstance(marketplaces, dict):
        marketplaces.pop(OFFICIAL_MARKETPLACE_NAME, None)
    return rec


def _purge_official_from_current(merged):
    """Remove every official-marketplace plugin entry from the merge result
    whose value is not exactly `False` (strings, null, objects, True are all
    removed; only an explicit `false` is kept), and drop the official
    marketplace registration."""
    enabled = merged.get("enabledPlugins")
    if isinstance(enabled, dict):
        merged["enabledPlugins"] = {
            k: v
            for k, v in enabled.items()
            if not (k.endswith(OFFICIAL_SUFFIX) and v is not False)
        }
    marketplaces = merged.get("extraKnownMarketplaces")
    if isinstance(marketplaces, dict):
        marketplaces.pop(OFFICIAL_MARKETPLACE_NAME, None)
    return merged


def _redact_leaves(obj):
    """Deep-copy obj, replacing every leaf value with REDACTED."""
    if isinstance(obj, dict):
        return {k: _redact_leaves(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_leaves(v) for v in obj]
    return REDACTED


def _is_secret_key(key):
    return key == "apiKeyHelper" or bool(_SECRET_KEY_RE.search(key))


def _redact_settings(obj, _top=True):
    """Deep-copy obj with secret-bearing values replaced by REDACTED:
    every value under the top-level `env` object, every value whose key
    matches (case-insensitively) key|token|secret|password|credential, and
    `apiKeyHelper`, at any depth."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "env" or _is_secret_key(k):
                result[k] = _redact_leaves(v) if isinstance(v, (dict, list)) else REDACTED
            else:
                result[k] = _redact_settings(v, _top=False)
        return result
    if isinstance(obj, list):
        return [_redact_settings(v, _top=False) for v in obj]
    return obj


def _path_is_secret(path):
    if not path:
        return False
    segments = path.split(".")
    return any(seg == "env" or _is_secret_key(seg) for seg in segments)


def merge(current, recommended, mode, no_official=False, purge_official=False, redact=True):
    """Merge current settings with the recommendation.

    Returns (merged: dict, drift: list[str]). drift entries have the form
    "<dotted.path>: recommended=<json> current=<json>" (the CLI prefixes
    each with "drift: " when printing to stderr). When `redact` is true
    (the default), drift entries whose path is secret-bearing (see
    _redact_settings) report "<redacted>" instead of the real values.
    """
    if mode not in ("enforce", "defaults"):
        raise ValueError("mode must be 'enforce' or 'defaults'")

    current = dict(current or {})
    recommended = copy.deepcopy(dict(recommended or {}))

    schema_value = current.pop("$schema", None)
    recommended.pop("$schema", None)

    if no_official or purge_official:
        recommended = _strip_official(recommended)

    drift_pairs = []
    merged = _merge_dict(current, recommended, mode, "", drift_pairs)

    if purge_official:
        merged = _purge_official_from_current(merged)

    if "enabledPlugins" not in merged:
        merged["enabledPlugins"] = {}
    merged["enabledPlugins"][ENGINEERING_PLUGIN_KEY] = True

    final = {"$schema": schema_value if schema_value is not None else SCHEMA_URL}
    final.update(merged)

    drift = []
    for path, rec_v, cur_v in drift_pairs:
        if redact and _path_is_secret(path):
            rec_repr = _canon_json(REDACTED)
            cur_repr = _canon_json(REDACTED)
        elif redact:
            # a whole-entry value (marketplace or MCP server) may itself carry env or keys
            rec_repr = _canon_json(_redact_settings(rec_v))
            cur_repr = _canon_json(_redact_settings(cur_v))
        else:
            rec_repr = _canon_json(rec_v)
            cur_repr = _canon_json(cur_v)
        drift.append("%s: recommended=%s current=%s" % (path, rec_repr, cur_repr))
    return final, drift


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_arg_parser():
    parser = argparse.ArgumentParser(prog="merge_settings.py")
    parser.add_argument("--current", required=True)
    parser.add_argument("--recommended", required=True)
    parser.add_argument("--mode", required=True, choices=["enforce", "defaults"])
    parser.add_argument("--no-official", action="store_true")
    parser.add_argument("--purge-official", action="store_true")
    parser.add_argument("--drift-report", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--no-redact",
        action="store_true",
        help=(
            "Do not redact secret-bearing values (env.*, keys matching "
            "key|token|secret|password|credential, apiKeyHelper) in "
            "--drift-report and --diff output. For tests only; never use "
            "this when settings may contain real secrets."
        ),
    )
    return parser


def main(argv=None):
    # The output is JSON consumed by install.sh through a pipe; it is UTF-8 regardless of the
    # console code page (Windows defaults to cp1252, which cannot encode every settings value).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _build_arg_parser().parse_args(argv)

    try:
        current = load_current(args.current)
    except UnusableSettings as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 3

    try:
        recommended = load_current(args.recommended)
    except UnusableSettings as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 3

    merged, drift = merge(
        current,
        recommended,
        args.mode,
        no_official=args.no_official,
        purge_official=args.purge_official,
        redact=not args.no_redact,
    )

    if args.drift_report:
        for line in drift:
            sys.stderr.write("drift: %s\n" % line)

    if args.check:
        return 0 if same(merged, current) else 10

    if args.diff:
        diff_current = current if args.no_redact else _redact_settings(current)
        diff_merged = merged if args.no_redact else _redact_settings(merged)
        before = json.dumps(diff_current, indent=2, ensure_ascii=False) + "\n"
        after = json.dumps(diff_merged, indent=2, ensure_ascii=False) + "\n"
        diff_lines = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="current",
            tofile="merged",
        )
        sys.stdout.writelines(diff_lines)
        return 0

    out = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
