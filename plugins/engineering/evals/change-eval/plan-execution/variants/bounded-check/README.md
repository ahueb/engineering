# Variant: bounded-check

The shipped `plugins/engineering` plugin plus one added instruction in
`skills/plan-execution/SKILL.md`'s fan-out dispatch (step 2): an
implementer may run the package's own unit tests or type check once,
capped at 60 seconds, before returning.

`run.sh` builds this variant at run time the same way it builds
`variants/current` (a fresh copy of the live `plugins/engineering`
directory into a temp directory), then applies `skill.patch` to that
copy with:

```
patch -p1 -d <copy-dir> < variants/bounded-check/skill.patch
```

`skill.patch` is a unified diff against
`skills/plan-execution/SKILL.md` as committed in this repository. If the
shipped skill's fan-out dispatch text changes, this patch may need to be
regenerated; `run.sh` fails loudly (patch exits non-zero) rather than
silently running an unpatched variant.
