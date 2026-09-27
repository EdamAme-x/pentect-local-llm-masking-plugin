"""Explicit setup only: download pinned weights, then verify offline loading."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

MODELS = {
    "google/gemma-4-E2B-it": "3e22461f65e89153144f8adb70e3b8c2cc9845a7",
    "Qwen/Qwen3-4B": "1cfa9a7208912126459214e8b04321603b3df60c",
}
ROOT = Path.home() / ".pentect" / "local-llm-masking"

def run(argv):
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace",
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
        if process.wait():
            raise RuntimeError("Setup subprocess failed")

def main():
    os.chdir(Path(__file__).resolve().parent)
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--model", choices=list(MODELS), default="google/gemma-4-E2B-it")
    args = parser.parse_args()
    model, revision = args.model, MODELS[args.model]
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        raise SystemExit("Python 3.10 through 3.13 is required by the pinned runtime")
    if args.prepare:
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from huggingface_hub import snapshot_download
        checkpoint = ROOT / ("checkpoint-" + revision)
        snapshot_download(model, revision=revision, local_dir=checkpoint,
                          allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "LICENSE*", "README.md"])
        state = {"device": args.profile, "model": model, "revision": revision, "checkpoint": str(checkpoint),
                 "environment": "venv-cuda" if args.profile == "cuda" else "venv"}
        # Child process starts with offline flags set before importing the runtime.
        os.environ["HF_HUB_OFFLINE"] = "1"
        code = "from server import LocalLLM; d=LocalLLM(str(checkpoint), device=DEVICE); d.inspect('No private information here.')"
        code = code.replace("str(checkpoint)", repr(str(checkpoint)))
        code = code.replace("DEVICE", repr(args.profile))
        # The approved plugin directory must not gain __pycache__ files.
        run([sys.executable, "-B", "-c", code])
        temporary = ROOT / "setup.json.tmp"
        temporary.write_text(json.dumps(state), encoding="utf-8")
        os.replace(temporary, ROOT / "setup.json")
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    environment = ROOT / ("venv-cuda" if args.profile == "cuda" else "venv")
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        run([sys.executable, "-m", "venv", str(environment)])
    wheel_suffix = "" if sys.platform == "darwin" else ("+cu128" if args.profile == "cuda" else "+cpu")
    torch_version = "2.8.0" if args.profile == "cuda" else "2.6.0"
    torch_args = [str(python), "-m", "pip", "install", "torch==" + torch_version + wheel_suffix]
    if sys.platform != "darwin":
        torch_args += ["--index-url", "https://download.pytorch.org/whl/" + ("cu128" if args.profile == "cuda" else "cpu")]
    elif args.profile == "cuda":
        raise SystemExit("CUDA is not supported on macOS")
    run(torch_args)
    run([str(python), "-m", "pip", "install", "transformers==5.17.0",
         "huggingface-hub==1.33.0", "sentencepiece==0.2.1"])
    os.chdir(Path(__file__).resolve().parent)
    run([str(python), str(Path(__file__).resolve()), "--prepare", "--profile", args.profile, "--model", args.model])
    print("Setup complete. Runtime inspection is offline.")

if __name__ == "__main__":
    main()
