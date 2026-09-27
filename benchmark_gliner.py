"""Run after generative benchmarks, without competing GPU workloads."""
import argparse
import importlib.util
import json
import platform
from pathlib import Path
import time
import torch
from benchmark import fixtures, heldout_fixtures, evaluate

parser = argparse.ArgumentParser()
parser.add_argument("--device", default="cuda")
parser.add_argument("--output", default="results/gliner.json")
parser.add_argument("--checkpoint", default="/workspace/gliner-checkpoint")
parser.add_argument("--bridge", default="gliner_server.py")
parser.add_argument("--heldout", action="store_true")
args = parser.parse_args()
spec = importlib.util.spec_from_file_location("gliner_bridge", args.bridge)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
torch.set_num_threads(4)
started = time.perf_counter()
detector = bridge.Detector(args.checkpoint, device=args.device)
report = {"model": bridge.MODEL, "revision": bridge.REVISION, "device": args.device,
          "python": platform.python_version(), "torch": torch.__version__, "cpu_threads": 4,
          "load_seconds": time.perf_counter() - started, "synthetic_only": True, "results": []}
for threshold in [0.2, 0.3, 0.5]:
    detector.threshold = threshold
    result = {"threshold": threshold, **evaluate(detector, heldout_fixtures() if args.heldout else fixtures(), torch, 2)}
    report["results"].append(result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)
path = Path(args.output)
path.parent.mkdir(exist_ok=True, parents=True)
path.write_text(json.dumps(report, indent=2), encoding="utf-8")
