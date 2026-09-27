"""Run explicitly after setup; not part of download-free unit CI."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
keep = {"HOME", "USERPROFILE", "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
env = {key: value for key, value in os.environ.items() if key.upper() in keep}
requests = [{"schema": "pentect.plugin.v1", "id": i, "hook": "inspect", "payload": {"text": text}}
            for i, text in enumerate(["", "password=SyntheticOnly!83q", "password=SyntheticOnly!83q"], start=1)]
result = subprocess.run([sys.executable, str(root / "server.py")], env=env, cwd=root,
    input="".join(json.dumps(r) + "\n" for r in requests), text=True, capture_output=True, timeout=180,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
if result.returncode:
    print(result.stderr)
    raise SystemExit("Real model subprocess failed")
responses = [json.loads(line) for line in result.stdout.splitlines()]
assert [r["id"] for r in responses] == [1, 2, 3]
assert responses[0]["spans"] == []
assert any(s["start"] == 9 and s["end"] == 26 and s["label"] == "SECRET" for s in responses[1]["spans"])
assert responses[1]["spans"] == responses[2]["spans"]
assert "SyntheticOnly!83q" not in result.stdout
print("Real offline model + sanitized environment + persistent protocol: passed")
