# Variant: current

The shipped `plugins/engineering` plugin, unmodified.

There is no stored copy of the plugin here (a stored copy would drift
from the real skill). `run.sh` builds this variant at run time by
copying the live `plugins/engineering` directory into a temp directory
and pointing `--plugin-dir` at that copy, so every benchmark run tests
whatever is currently committed.
