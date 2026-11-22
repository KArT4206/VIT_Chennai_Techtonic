"""Single-GPU job queue for Blender: one render job at a time, FIFO-ish via an exclusive file lock.

    python3 research/gpuq.py [--log FILE] -- <command ...>

1. Takes an exclusive fcntl lock on research/.gpu.lock (blocks while another queued job holds it).
2. Then waits until no *un-queued* `Blender -b` process is running (jobs started outside the queue are never
   interrupted, only waited for).
3. Runs the command, records wall time, exit code and queue wait to research/.gpuq_log.jsonl.
Exit code is the command's exit code.
"""
import fcntl, json, os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]
log = None
if "--log" in a:
    i = a.index("--log"); log = a[i + 1]; del a[i:i + 2]
cmd = a[a.index("--") + 1:]
t0 = time.time()
with open(os.environ.get("GPUQ_LOCK", os.path.join(here, ".gpu.lock")), "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    def others():
        # only real background Blender processes (process name exactly 'Blender' with a -b flag); queue wrappers,
        # shells and an interactive Blender window are ignored
        pids = subprocess.run(["pgrep", "-x", "Blender"], capture_output=True, text=True).stdout.split()
        busy = []
        for p in pids:
            args = subprocess.run(["ps", "-o", "args=", "-p", p], capture_output=True, text=True).stdout.split()
            if "-b" in args or "--background" in args:
                busy.append(p)
        return busy
    while os.environ.get("GPUQ_IGNORE_BLENDER") != "1" and others():   # test hook only
        time.sleep(5)
    t1 = time.time()
    with (open(log, "w") if log else open(os.devnull, "w")) as fh:
        rc = subprocess.call(cmd, stdout=fh if log else None, stderr=subprocess.STDOUT if log else None)
    t2 = time.time()
    rec = dict(cmd=" ".join(cmd)[:400], queued_s=round(t1 - t0, 1), run_s=round(t2 - t1, 1), rc=rc, finished=time.strftime("%Y-%m-%dT%H:%M:%S"))
    open(os.environ.get("GPUQ_JOBLOG", os.path.join(here, ".gpuq_log.jsonl")), "a").write(json.dumps(rec) + "\n")
    print("[gpuq]", json.dumps(rec), flush=True)
sys.exit(rc)
