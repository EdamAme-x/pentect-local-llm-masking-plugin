# Masking model screening — 2026-09-28

## Decision

**Gemma 4 E2B IT, unquantized, prompt v1** is the initial quality-oriented default.
Qwen3 4B is a faster alternative with more over-masking in this screening. Neither
is a production privacy guarantee. The very small models tested here are not
reliable enough to replace Pentect's deterministic detectors.

GLiNER PII small is a separate, opt-in official plugin candidate. It is much
faster, including on CPU, but has substantial false positives and poorer Japanese
coverage. It is not the generative LLM backend requested for this repository.

## Method

- One RTX 4090, 24 GB, driver 580.159.04, rented from RunPod. CPU host: AMD EPYC
  75F3. CPU inference uses four PyTorch threads.
- Synthetic data only: 41 initial cases (31 annotated entities, 10 clean cases).
  An additional 18 Japanese-heavy cases contain 12 entities and 6 clean cases.
  No user messages, API keys, or actual customer records were uploaded.
- GPU runs repeat each case twice. Repeats are not independent examples.
- Greedy generation, thinking disabled, at most 768 generated tokens; exact
  source-substring alignment, no regex detector assistance.
- Full-entity coverage counts an entity only if every annotated byte is masked.
  It can reward over-masking, so byte precision and exact typed matches are also
  recorded. Byte precision is correct masked bytes / all masked bytes.
- Malformed output or failed inference is an error and counts as a miss for
  annotated entities. An error on a clean input is not proof of correct handling.
- Latency excludes weight loading/download and one warmup request. Failed and
  empty responses remain included, so low latency alone can be misleading.
- All checkpoint revisions, per-case numbers, dataset fingerprints, and runtime
  versions are in the JSON files under [results](results/). No raw model responses
  are retained. This is a small screening exercise, not a validated benchmark.

## Initial GPU screening, prompt v1

Times are seconds. Errors are over 82 requests. Coverage is full-entity coverage.

| Model | Coverage | Byte precision | p50 | p95 | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3 0.6B | 22.6% | 47.3% | 0.148 | 1.506 | 6 |
| Qwen3 1.7B | 71.0% | 35.8% | 1.106 | 3.092 | 28 |
| Qwen3 4B | 93.5% | 70.2% | 0.771 | 1.547 | 2 |
| SmolLM2 360M | 54.8% | 28.5% | 0.860 | 17.112 | 26 |
| SmolLM2 1.7B | 51.6% | 18.5% | 0.907 | 2.277 | 32 |
| Qwen3.5 0.8B | 74.2% | 35.4% | 1.033 | 2.153 | 4 |
| Qwen3.5 2B | 38.7% | 56.0% | 0.145 | 1.576 | 0 |
| Qwen3.5 4B | 54.8% | 97.8% | 0.187 | 1.604 | 4 |
| Gemma 4 E2B IT | 96.8% | 90.0% | 1.435 | 2.122 | 0 |

The first five models used Transformers 4.57.1 / PyTorch 2.4.1; the final four
used Transformers 5.17.0 / PyTorch 2.6.0. GPU weights use FP16. Qwen3.5 used
reference PyTorch kernels, not optional causal-convolution/FLA acceleration.
These are measured implementations, not claims about the best possible speed
of each architecture. Some setup/CPU work ran concurrently; timing is indicative,
not an isolated machine benchmark.

## Follow-up: prompt sensitivity and Japanese cases

Prompt v2 added value-only instructions and examples. It was evaluated on the
new runtime, so differences from the first five baseline rows are not a clean
prompt-only causal experiment.

| Configuration | Initial coverage / precision | Japanese-heavy coverage / precision |
| --- | --- | --- |
| Qwen3 4B, v1 | 93.5% / 70.2% | 100% / 66.8% |
| Qwen3 4B, v2 | 96.8% / 93.8% | 83.3% / 96.3% |
| Gemma 4 E2B, v1 | 96.8% / 90.0% | 100% / 96.9% |
| Gemma 4 E2B, v2 | 93.5% / 93.6% | 100% / 100% |

Gemma v1 exactly typed all 12 Japanese-heavy entities, with one false-positive
clean case. V2 removed that false positive but introduced an initial-set long-log
error. Keep v1 as the conservative starting configuration; do not optimize only
for one small test set. The follow-up set informed this choice and is therefore
not an untouched final test set. A larger external holdout is still needed.

## Quantization

BitsAndBytes NF4, double quantization, FP16 compute on the same GPU:

| Configuration | Coverage | Byte precision | p50 | Peak allocated GPU bytes |
| --- | ---: | ---: | ---: | ---: |
| Qwen3 4B, 4bit, v1 | 87.1% | 90.4% | 1.066 s | 3,256,216,576 |
| Qwen3 4B, 4bit, v2 | 90.3% | 93.6% | 1.257 s | 2,985,364,480 |
| Gemma 4 E2B, 4bit, v1 | 61.3% | 65.8% | 1.634 s | 7,155,437,568 |

Unquantized initial runs allocated about 8.36 GB for Qwen3 4B and 10.41 GB for
Gemma. These are PyTorch peak allocations, not total process/device memory.
Quantization saved memory but did not improve latency or coverage here. It is
not the default. Other quantizers and inference engines were not tested.

## GLiNER comparator

At threshold 0.3, initial coverage was 83.9%, byte precision 68.9%, with no
inference errors. Seven of ten clean cases had false positives. Japanese-heavy
coverage fell to 66.7%, with three of six clean cases falsely marked.

Median latency: RTX 4090 **14.4 ms**, RunPod CPU **50.0 ms**, this Windows PC
(Core Ultra 9 285K, four threads) **43.3 ms**. Windows p95 was 56.8 ms. Thresholds
0.2 and 0.5 were also measured; all per-case results are included.

Actual Windows integration was tested through project-scoped installation and
`pentect mask`: synthetic name/email became handles. A Windows environment/cache
startup bug was found and fixed before this test passed. Unit tests do not claim
model recall, and this live check does not validate every agent integration.

## Local Windows CPU follow-up

Core Ultra 9 285K, four threads, FP32, Transformers 5.17.0 / PyTorch 2.6.0:

| Configuration | Dataset | p50 | p95 | Coverage | Errors |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3 4B, v2 | Initial 41 cases, once | 12.27 s | 18.64 s | 96.8% | 1 |
| Gemma 4 E2B, v1 | Japanese-heavy 18 cases, once | 7.13 s | 9.94 s | 100% | 0 |

These rows use different datasets and must not be read as an apples-to-apples CPU
ranking. They show why GPU latency must not be advertised as CPU latency. Local
setup/smoke work overlapped part of the Qwen run. Gemma's actual Pentect request
also took about 8.5 seconds on CPU, after a roughly 14-second cold start. It masked
the synthetic email but missed the isolated first name "Alice" in that smoke
sentence. A direct secret-value smoke passed. Local generation remains a heavy
optional layer, not a low-latency replacement for deterministic matching.

## Local RTX 5080 follow-up

Windows, RTX 5080 16 GB, driver 576.88, PyTorch 2.8.0+cu128, Transformers 5.17.0,
FP16, Gemma v1, one pass per case:

| Dataset | p50 | p95 | Coverage | Byte precision | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial 41 cases | 1.71 s | 2.37 s | 96.8% | 90.0% | 0 |
| Japanese-heavy 18 cases | 1.60 s | 2.21 s | 100% | 96.9% | 0 |

This reproduced the tested RunPod predictions on the user's actual GPU. Peak
allocated GPU memory was about 10.41 GB. The CUDA installer uses a separate
environment so it does not overwrite the CPU runtime. This does not establish
performance on lower-memory GPUs. Runtime adds a bounded hash/span cache for
repeated text; **all benchmark rows above bypass that cache**.

## Sources and reproduction

The dedicated RunPod resource was deleted after result retrieval and its absence
verified via the RunPod API. The GPU-time estimate is approximately **$0.44** at
$0.74/hour, versus the authorized $50 ceiling. This is not a finalized billing
statement and excludes any separately billed storage/network charges. No
pre-existing pods were modified.

- [Gemma 4 E2B IT](https://huggingface.co/google/gemma-4-E2B-it)
- [Qwen3 4B](https://huggingface.co/Qwen/Qwen3-4B)
- [Qwen3.5 0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B)
- [GLiNER PII small](https://huggingface.co/knowledgator/gliner-pii-small-v1.0)

Use the pinned revisions in `benchmark.py`, the runtime versions in each JSON,
and the flags reflected by its filename. `--heldout` selects the follow-up cases;
`--prompt-v2` changes the prompt; `--quantize` selects NF4. The default plugin
installer pins the modern runtime and Gemma checkpoint. CPU uses FP32, not GPU
FP16. It must be measured separately before assuming desktop responsiveness.
