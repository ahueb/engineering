#!/usr/bin/env python3
"""Run a command on a pty and answer one prompt, then echo everything it wrote.

    pty_run.py MARKER INPUT CMD [ARG...]

INPUT (use a trailing \\n) is written to the pty only once MARKER appears in the
child's output. Waiting matters: the `claude` CLI puts the terminal in raw mode
and would swallow an answer queued before the prompt is printed.

Used by ci.sh to exercise install.sh's interactive /dev/tty migration prompt,
which is skipped entirely without a controlling terminal. Exits with the child's
status (128+signal if killed, 124 on the safety timeout).
"""
import errno
import os
import pty
import select
import signal
import sys
import time

TIMEOUT = float(os.environ.get("PTY_RUN_TIMEOUT", "600"))


def main():
    if len(sys.argv) < 4:
        sys.stderr.write("usage: pty_run.py MARKER INPUT CMD [ARG...]\n")
        return 2
    marker = sys.argv[1].encode()
    answer = sys.argv[2].encode()
    argv = sys.argv[3:]

    pid, fd = pty.fork()
    if pid == 0:  # child: the pty slave is stdin/stdout/stderr and the ctty
        os.execvp(argv[0], argv)
        os._exit(127)

    chunks = []
    sent = False
    timed_out = False
    deadline = time.time() + TIMEOUT
    while True:
        if time.time() > deadline:
            timed_out = True
            os.kill(pid, signal.SIGKILL)
            break
        try:
            ready, _, _ = select.select([fd], [], [], 0.5)
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            break
        if not ready:
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:  # EIO on Linux once the slave side is closed
            break
        if not data:
            break
        chunks.append(data)
        if not sent and marker in b"".join(chunks):
            try:
                os.write(fd, answer)
            except OSError:
                pass
            sent = True

    try:
        os.close(fd)
    except OSError:
        pass
    _, status = os.waitpid(pid, 0)
    sys.stdout.buffer.write(b"".join(chunks))
    if not sent:
        sys.stdout.buffer.write(b"\npty_run.py: marker never appeared; nothing sent\n")
    sys.stdout.buffer.flush()
    if timed_out:
        return 124
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


if __name__ == "__main__":
    sys.exit(main())
