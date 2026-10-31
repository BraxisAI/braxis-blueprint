#!/usr/bin/env python3
"""kit_sandbox.py — a small, disposable Python sandbox for KIT.

The container has no network, no host mounts, a read-only root, a 512 MB
memory cap, one CPU, a 128-process limit, and nobody as the user. Code is
fed on stdin; the only writable path is a 64 MB tmpfs at /tmp. The host does
not expose a shell or a volume.

The image is `braxis-kit-sandbox:1`, built from `kit-sandbox.Dockerfile`.
It bakes in numpy, pandas, matplotlib, Pillow, scipy, sympy and networkx.
Packages are installed at BUILD time only; runtime `pip install` is not
available and the runtime has no network. Do not turn the sandbox into a
package-install service: that would let generated code fetch unreviewed code.

Docker is the boundary here. Do not replace it with `exec()` and a timeout:
a timeout is not a sandbox.
"""
import os
import shutil
import subprocess
import time
import uuid

IMAGE = os.environ.get("KIT_SANDBOX_IMAGE", "braxis-kit-sandbox:1")


def available():
    return bool(shutil.which("docker"))


def run(code, timeout=6, max_output=12000):
    code = str(code or "")
    if not code.strip():
        return {"ok": False, "error": "empty code"}
    if len(code) > 6000:
        return {"ok": False, "error": "code too long (6000 char limit)"}
    if "\x00" in code:
        return {"ok": False, "error": "NUL byte in code"}
    if not available():
        return {"ok": False, "error": "docker not available on this host"}
    name = "kit-sbx-" + uuid.uuid4().hex[:12]
    cmd = [
        "docker", "run", "--rm", "-i", "--name", name,
        "--network", "none",
        "--ipc", "none",
        "--memory", "512m", "--memory-swap", "512m",
        "--cpus", "1.0", "--pids-limit", "128",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--ulimit", "nofile=64:64",
        "-e", "HOME=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        # Cap output inside the container so a printer cannot fill the host
        # process's capture buffer before the timeout fires. Keep Python's
        # exit status: piping straight to head would report head's status and
        # mark a SyntaxError as a successful run.
        IMAGE, "sh", "-c",
        "python -I - >/tmp/kit_out 2>&1; rc=$?; head -c 12000 /tmp/kit_out; exit $rc",
    ]
    start = time.time()
    try:
        p = subprocess.run(cmd, input=code, capture_output=True, text=True,
                           timeout=timeout + 2)
        out = (p.stdout or "")[:max_output]
        err = (p.stderr or "")[:max_output]
        return {"ok": p.returncode == 0, "returncode": p.returncode,
                "stdout": out, "stderr": err,
                "seconds": round(time.time() - start, 2),
                "timed_out": False}
    except subprocess.TimeoutExpired as e:
        # Kill the container, not just the docker client. --rm removes it.
        try:
            subprocess.run(["docker", "kill", name], capture_output=True,
                           timeout=10)
        except Exception:
            pass
        out = (e.stdout or b"")
        err = (e.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return {"ok": False, "returncode": None, "stdout": out[:max_output],
                "stderr": err[:max_output], "seconds": round(time.time() - start, 2),
                "timed_out": True, "error": "timeout after %ss" % timeout}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "seconds": round(time.time() - start, 2)}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(run(sys.stdin.read() or "print(2+2)"), indent=1))
