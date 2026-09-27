# Pentect Local LLM Masking

Experimental **local generative LLM** detector for Pentect. The model extracts
candidate values; a deterministic bridge accepts only exact substrings of the
original input and returns UTF-8 byte ranges. Pentect owns masking and restoration.
No cloud inference API, HTTP listener, or remote tool execution is involved.

This is research software, not a guarantee that all secrets are found. Keep
Pentect's built-in detectors enabled. Installing this plugin also opts into its
PII detection independently of Pentect's built-in PII options.

## Install

Python 3.10–3.13 is required. Setup downloads pinned weights and dependencies into
`~/.pentect/local-llm-masking`, then checks offline inference.

The current default is **Gemma 4 E2B IT**, selected for the best masking quality
among the tested configurations. Despite its effective parameter count, this
multimodal checkpoint needs substantial memory: allow 25 GB disk and 24 GB RAM
for CPU use, or roughly 11 GB GPU memory. Only text is used by this plugin.

```sh
pentect plugins add github:@EdamAme-x/pentect-local-llm-masking-plugin --profile cpu
```

CPU is the default. A compatible NVIDIA GPU can use `--profile cuda` (PyTorch
2.8.0 / CUDA 12.8; CPU uses PyTorch 2.6.0). CPU and CUDA use separate managed
environments and share checkpoints. Keeping both requires extra disk space. The native
Command process has your OS permissions: inspect the source before approving it.
Runtime sets `HF_HUB_OFFLINE=1`; model downloads happen only during setup.

For the faster Qwen3 4B alternative, run the following from a trusted checkout,
then re-run the live smoke test:

```sh
python setup.py --model Qwen/Qwen3-4B --profile cpu
```

This switches the managed model used by the plugin. Normal plugin setup returns to
the Gemma default. See [measured tradeoffs](BENCHMARKS.md) before switching.

The manifest uses `required = true`. Malformed JSON, hallucinated substrings,
truncated generation, oversized input, or model failures return a value-free
error code and cause Pentect to block the request. Successful but incorrect
predictions, including empty lists, can still miss secrets.

## Design limits

- Inspects 3,500-character windows with 500 characters of overlap. Context and
  entities crossing those bounds can be missed. Inputs are not silently truncated
  to a token limit: oversized tokenized windows fail inspection.
- Extracts secrets, names, email addresses, phone numbers, addresses, and account
  numbers. Labels and exact substring membership are validated.
- A reported value masks every identical occurrence within that window, even if
  another occurrence is harmless. The model can still select an overly broad or
  incomplete substring. Exact membership is not a semantic correctness proof.
- Untrusted document instructions can affect statistical predictions despite
  prompt separation. Do not treat this model as an instruction security boundary.
- CPU inference can exceed Pentect's 60-second per-request limit on long inputs.
  Latency on a cloud GPU is not a prediction of laptop performance.
- The model is never asked to rewrite source text or create restoration handles.
- Repeated text uses a process-local LRU cache bounded to 64 entries and 16,384
  spans. It stores input hashes and ranges, not source strings, and is never
  written to disk. Failures are not cached. Published benchmarks bypass this
  cache and measure actual inference. Restart the agent after changing models.

## Tests and evaluation

```sh
python -m unittest discover -s tests -v
python benchmark.py --models Qwen/Qwen3-4B --device cuda --output results/run.json
```

`benchmark.py` uses synthetic data only. Its initial screening set has 41 unique
cases; repeats measure timing consistency, not additional independent examples.
`--heldout` selects separate Japanese-heavy cases. Reports include full-entity
coverage, byte precision, exact typed matches, clean false positives, errors,
latencies, runtime versions, and pinned checkpoint revisions. Errors count as
misses, not successful clean predictions. No raw user data or model output is
written into reports.

For the GLiNER comparator, place the official Pentect plugin's `server.py` next
to the benchmark as `gliner_server.py`; `benchmark_gliner.py` evaluates thresholds
0.2, 0.3, and 0.5. GLiNER is a span classifier, not the generative LLM backend.

Small synthetic screening results do not establish production recall. Model,
prompt, quantization, inference engine, and hardware all change the tradeoff.

## Remove

```sh
pentect plugins remove local-llm-masking
```

The downloaded environment remains under `~/.pentect/local-llm-masking`; remove
that directory separately if no longer needed. Integration code is MIT; model
weights retain their upstream licenses.
