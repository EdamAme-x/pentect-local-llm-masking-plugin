"""Create one bounded evaluation pod; delete on stop-file, deadline or Ctrl-C.
API key is read from stdin and never written to state, logs, or the pod.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--public-key", required=True)
    args = parser.parse_args()
    key = sys.stdin.readline().strip()
    def api(method, path, payload=None):
        req = urllib.request.Request("https://rest.runpod.io/v1/pods" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                     "User-Agent": "pentect-masking-evaluation/0.1"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as error:
            detail = error.read(1000).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
            print(json.dumps({"status": error.code, "detail": detail}), flush=True)
            raise
    state = Path(args.state)
    stop = state.with_suffix(".stop")
    pod_id = None
    try:
        pod = api("POST", "", {"name": "pentect-masking-eval-20260928", "cloudType": "SECURE",
            "computeType": "GPU", "gpuCount": 1, "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
            "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
            "containerDiskInGb": 70, "volumeInGb": 0, "ports": ["22/tcp"],
            "supportPublicIp": True, "env": {"PUBLIC_KEY": Path(args.public_key).read_text().strip()}})
        pod_id = pod["id"]
        safe = {k: pod.get(k) for k in ("id", "name", "costPerHr", "publicIp", "portMappings")}
        safe["lease_started"] = time.time()
        safe["lease_seconds"] = 7200
        state.write_text(json.dumps(safe), encoding="utf-8")
        print(json.dumps(safe), flush=True)
        if not isinstance(pod.get("costPerHr"), (int, float)) or pod["costPerHr"] > 1.2:
            raise RuntimeError("hourly cost cap")
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline and not stop.exists():
            time.sleep(10)
    finally:
        if pod_id:
            for attempt in range(12):
                try:
                    api("DELETE", "/" + pod_id)
                    print(json.dumps({"terminated": pod_id}), flush=True)
                    break
                except Exception:
                    if attempt == 11:
                        print("TERMINATION FAILED: manual cleanup required", flush=True)
                        raise
                    time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Lease failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
