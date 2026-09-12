# Fixture: six-package-migration

A six-package config-API migration, scaffolded by
`scaffold.sh <target-dir>`. Six independent "service" modules
(`src/services/svc1.py` .. `svc6.py`), each paired with its own test file,
currently call the deprecated `src/legacy_config.py` module. A new
`src/config.py` (`Config` class) is already implemented and pre-existing
in the repo; it is not owned by any package and must not be modified.

`plan.md` defines six tasks, one per service: migrate `svcN.py` away from
`legacy_config` to `config.Config()`, keeping behaviour identical (same
returned values), and drop the `legacy_config` import. Each task owns
exactly `src/services/svcN.py` and `tests/test_svcN.py` — disjoint files,
at least two files per package.

No wrong assumption is planted in this fixture. Test command:

```
python3 -m unittest discover -s tests -t . -v
```

Acceptance: all six `tests/test_svcN.py` continue to pass, and no
`src/services/*.py` file imports `legacy_config` anymore.
