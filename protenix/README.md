# Protenix v1 on the TSL HPC

This image runs **`protenix_base_default_v1.0.0`**, the Protenix-v1 base model. The application code is **Protenix 1.0.9**, pinned to commit [`510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d`](https://github.com/bytedance/Protenix/tree/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d). Code version and model version are different identifiers. This installation does not select the later-data-cutoff model or Protenix-v2.

The container supports offline prediction from prepared inputs. Download the image, model checkpoint and required data on **software23** first. GPU jobs use the local assets and precomputed MSAs; they do not search an online MSA service. General cluster facts and evidence dates remain in [HPC_COMPATIBILITY.md](../HPC_COMPATIBILITY.md).

## Verification status

**Published; CI installation checks passed on 6 November 2026.** [Successful CI run](https://github.com/georgedeeks/bio-containers/actions/runs/42250059849), built from recipe commit [`95c3727`](https://github.com/georgedeeks/bio-containers/tree/95c372703969523fcae3eff86e330c886da90b85/protenix). The public image was independently checked for anonymous access, Linux x86_64 architecture, the correct source/model labels and a matching immutable manifest digest. The pull command below selects those exact contents.

| Check | Status |
| --- | --- |
| Launcher, integrity/provenance and confidence-summary helpers | All 22 unit tests passed locally and in CI |
| Image build and offline CPU installation checks | Passed; unprivileged user, read-only image, no network |
| Official v1 assets and real-checkpoint CPU prediction | Passed in CI: five assets downloaded and checksummed; synthetic homodimer produced CIF, confidence JSON and summary CSV with one seed/sample/cycle/step |
| Recorded run provenance | Checked: completed status, correct model/code, archived asset-manifest hash; asset hashes matched between both successful CI runs |
| HPC SIF conversion and minimal container startup | User-reported 6 November 2026: SIF created; `/bin/true` returned exit 0 with the missing `rc_preload.so` default mount disabled |
| HPC Protenix startup and asset staging/check | Initial attempts were blocked before application startup by that mount; rerun with the workaround below, completion not yet reported |
| GPU startup and representative complex on TSL | Requester's test; not run here |
| Prediction accuracy or published benchmark reproduction | Not assessed |

CI checks installation without a GPU. A successful image build does not establish peak memory, runtime or prediction quality for a target complex. The requester owns the first GPU workload test; it is not an installer delivery gate.

## Runtime and model choices

- Linux x86_64, Python 3.12 and PyTorch 2.7.1 with CUDA 12.6 libraries. The container does not install or replace the host NVIDIA driver.
- The image uses a hash-locked inference dependency set, excluding unused training/notebook and optional accelerator packages. Application source is unchanged; its package dependency metadata is adapted to that set. The original upstream requirements, resolved packages and source revision remain under `/opt/container-info`.
- Native Torch triangle operations and LayerNorm avoid compiling optional CUDA extensions at startup. These choices may affect speed and numerical results compared with a different backend.
- The guarded `protenix-predict` command fixes the model name and requires prepared protein MSA paths. `--no-msa` is an explicit diagnostic option; do not treat its predictions as equivalent to a run with MSAs.
- This initial runner disables templates and RNA MSA and rejects RNA inputs. It uses 10 cycles, 200 diffusion steps, bf16 and native Torch kernels for production; sampling counts and seeds are explicit. Match these choices when comparing results.
- Model assets live outside the SIF in a persistent, site-mounted directory. Use absolute paths under `/hpc-home` or `/tsl`; no custom `--bind` mounts are required.
- Preserve the exact SIF digest, asset manifest, input JSON, seed list, diffusion samples per seed and runtime settings with an analysis. Keep different settings in different output directories.

## Pull the image and prefetch assets

Run in Bash on **software23**. Choose a writable installation path; the example follows the site's shared testing convention. The command pins the tested image digest. For a future update, use its successful Actions summary and a new SIF filename, preserving the previous working image.

```bash
ml load apptainer
export APPTAINER_TMPDIR="/tsl/scratch/$USER/apptainer-tmp"
export APPTAINER_CACHEDIR="/tsl/scratch/$USER/apptainer-cache"
INSTALL=/tsl/software/testing/Protenix/1.0.9/x86_64
SIF="$INSTALL/protenix.sif"
ASSETS="$INSTALL/assets"
apptainer_options=(--cleanenv)
if [[ ! -e /usr/local/lib64/rc_preload.so ]]; then
    apptainer_options+=(--no-mount /usr/local/lib64/rc_preload.so)
fi
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR" "$INSTALL" &&
apptainer pull "$SIF" docker://ghcr.io/georgedeeks/protenix@sha256:289dbfedc9205ec78864a90cf06ccbb3dfe42919243cdea3883b11d730f9db3f &&
apptainer exec "${apptainer_options[@]}" "$SIF" protenix-smoke-test &&
apptainer exec "${apptainer_options[@]}" "$SIF" protenix-assets download --root "$ASSETS" &&
apptainer exec "${apptainer_options[@]}" "$SIF" protenix-assets check --root "$ASSETS"
```

**Installer finish line:** after the SIF pull, startup check and final asset check succeed, hand over the SIF path, assets path and GPU-job guide. The installer needs no research project or scientific inputs. The remaining prediction examples are optional extra checks or requester work. A site loading wrapper can be added separately; the supplied Slurm script uses the SIF directly.

The commands are chained with `&&` so later steps stop if an earlier one fails. If the SIF already exists from a successful pull, keep it and rerun only the required `exec` commands. The host-specific option skips only the [observed missing default library mount](../HPC_COMPATIBILITY.md#missing-default-library-mount), preserving it on hosts where the file exists and retaining the shared storage mounts. This does not require rebuilding the image.

The installation smoke test checks imports, dependencies and native CPU kernels; it is not model inference or GPU validation. The asset commands also do not need a GPU. Complete the download and check before submitting an offline job. The tested OCI image downloads about 3.54 GB of compressed layers, and the five model/data assets total 2.13 GB; this excludes MSAs and prediction outputs. Allow additional space for SIF conversion, expanded layers and caches, and check your actual quota rather than the shared volume's free space. For private image access, updates without overwriting a working SIF, and shared software registration, follow the [installation guide](../ADDING_NEW_CONTAINER_GUIDE.md#4-pull-and-run-on-the-hpc).

**Known TSL cache warning:** `Cache disabled - cache location ... is not writable` can occur even when actual writes succeed; the [checked HPC behaviour](../HPC_COMPATIBILITY.md#shared-storage-permission-checks) records this for both of George's scratch cache/temp directories. `mkdir -p` alone does not resolve the permission-check mismatch. Once actual writes have been checked, use this in the installation shell for subsequent commands if affected:

```bash
export APPTAINER_DISABLE_CACHE=true
```

Keep `APPTAINER_TMPDIR` on writable scratch. This explicitly selects the cache-disabled behaviour Apptainer already used after the warning; it does not repair permissions. Let an in-progress pull finish, and continue after it succeeds and the startup check passes. A successfully pulled SIF does not need downloading again because of this warning. The model assets and application caches are separate from this optional image-download cache.

`protenix-assets check` verifies the downloaded assets against the locally recorded SHA256 manifest. Retain that manifest with the analysis; it records the files used and detects subsequent changes. It is not an independent upstream checksum certification.

## Reduced CPU installation test

**Optional: not required for installer handover.** This prediction check already passed in CI. Anyone repeating it on the HPC supplies their own writable output location and compute allocation.

CI also runs a tiny offline prediction with the real v1 checkpoint, an artificial 20-residue homodimer, one seed/sample/recycle/diffusion step and fp32. It runs without a GPU, as an unprivileged user with a read-only image and assets. This checks installation and output plumbing; the artificial structure and confidence scores have no scientific interpretation. The [workflow](../.github/workflows/build-protenix.yml) retains its small output/log and asset-manifest records.

```bash
SIF=/tsl/software/testing/Protenix/1.0.9/x86_64/protenix.sif
ASSETS=/tsl/software/testing/Protenix/1.0.9/x86_64/assets
apptainer_options=(--cleanenv)
if [[ ! -e /usr/local/lib64/rc_preload.so ]]; then
    apptainer_options+=(--no-mount /usr/local/lib64/rc_preload.so)
fi
apptainer exec "${apptainer_options[@]}" "$SIF" protenix-predict --cpu-smoke-test \
    --assets "$ASSETS" --input /opt/protenix-example-smoke.json \
    --out-dir /tsl/PROJECT/protenix/cpu-installation-check
```

The CPU option accepts only the bundled synthetic input and cannot silently turn a real workload into a reduced test. Do not run this CPU-intensive check on a submission node; use an appropriate compute allocation. Its successful completion is separate from the requester’s GPU test.

## Prepare the input

Use the [pinned upstream input schema](https://github.com/bytedance/Protenix/blob/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d/docs/infer_json_format.md). Each job has a name and molecular entities. For protein MSAs, use the documented `pairedMsaPath` and `unpairedMsaPath` fields with readable absolute paths on the HPC. Prepare MSAs and any other required input data before running on an offline compute node.

The prediction command preserves the supplied JSON and writes `run-info.json` with model/code versions, settings, seeds, and SHA256 hashes of the input JSON and referenced MSA/ligand files. It also saves the asset manifest alongside the predictions. Keep the referenced input files unchanged during a run. Use unique job names and a new output directory for each run. Do not combine output trees from different checkpoints, input sequences or inference settings merely because the job names match.

For a first installation check, choose a small, representative complex whose inputs are ready. One seed and one diffusion sample establish that the GPU workflow runs; they do not provide an across-seed SD or a full accuracy benchmark. An explicitly MSA-free diagnostic can use `--no-msa`, but record that change when interpreting its results.

## Run a GPU job

Download [run.slurm](https://raw.githubusercontent.com/georgedeeks/bio-containers/5700f98624047b907b2996e67196e0cdc2218033/protenix/run.slurm) to your project directory. After staging assets on software23, return to a submission/login node and change to that directory before submitting. Its arguments are the SIF, assets, prepared input, new output directory, comma-separated seeds, and samples per seed. Replace `PROJECT` and the input filename with real paths:

```bash
SIF=/tsl/software/testing/Protenix/1.0.9/x86_64/protenix.sif
ASSETS=/tsl/software/testing/Protenix/1.0.9/x86_64/assets
INPUT=/tsl/PROJECT/protenix/input-with-msas.json
OUTPUT=/tsl/PROJECT/protenix/first-gpu-test
sbatch run.slurm "$SIF" "$ASSETS" "$INPUT" "$OUTPUT" '101' 1
```

Use [run.slurm](run.slurm) as the resource request to review and adjust for your target. Its first workload test must check that PyTorch sees the allocated GPU and that Protenix writes predictions without errors. The script requests `tsl2048n2` because that is the node with recorded A100 80 GB and driver evidence; this restricts scheduling to that node. Do not assume every GPU node has the same driver or memory. Preserve the scheduler's device assignment when using `--cleanenv`, as the supplied script does.

After the first test, a multi-seed run uses a new output directory and an explicit sampling budget. For example, five seeds with five diffusion samples each produce 25 predicted structures per successfully completed job:

```bash
OUTPUT=/tsl/PROJECT/protenix/five-seed-run
sbatch run.slurm "$SIF" "$ASSETS" "$INPUT" "$OUTPUT" '101,102,103,104,105' 5
```

These values illustrate the interface; they are not a reproduction of a published benchmark. For a chosen benchmark, match its model, input preprocessing, MSA/template settings, sampling budget and evaluation procedure explicitly.

## Summarize ipTM across seeds

[summarize-confidence.py](https://raw.githubusercontent.com/georgedeeks/bio-containers/95c372703969523fcae3eff86e330c886da90b85/protenix/summarize-confidence.py) needs only Python's standard library. Download it beside `run.slurm`, or use the same helper inside the image as `apptainer exec "${apptainer_options[@]}" "$SIF" protenix-summarize` after defining the host-specific options above. Run it against one output tree, after checking Slurm logs and any Protenix `ERR` files:

```bash
python3 summarize-confidence.py /tsl/PROJECT/protenix/five-seed-run \
    --output-dir /tsl/PROJECT/protenix/five-seed-summary \
    --expected-seeds 101,102,103,104,105 --expected-samples 5
```

It writes four files and refuses to overwrite an existing report:

| File | Contents |
| --- | --- |
| `per_sample.csv` | Every predicted structure's job, seed, sample label, ipTM, optional pTM/ranking score and source JSON |
| `per_seed.csv` | Arithmetic mean ipTM over that seed's diffusion samples, sample count and within-seed sample SD |
| `across_seeds.csv` | Equal-weight mean of seed means and **sample SD across seed means** (`ddof=1`), separately for each job |
| `summary.json` | The same across-seed results plus source path, expected counts and the aggregation definition |

**The seed is the unit for the across-seed summary.** First average all diffusion samples within each seed; then give each seed mean one equal vote. No maximum or best-ranked sample is selected. Unequal sample counts therefore do not give a seed extra weight; supplying `--expected-samples` rejects missing or extra sample labels. A single observation has unavailable SD (blank CSV cell / JSON `null`), not zero. This SD describes variation between seed means; it is not a standard error or confidence interval.

The parser follows the pinned [output writer](https://github.com/bytedance/Protenix/blob/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d/runner/dumper.py): `JOB/seed_N/predictions/JOB_summary_confidence_sample_K.json`. The sample suffix is normally a rank within a seed; it is not another random seed. Missing/nonfinite ipTM, unexpected layouts and duplicate identifiers fail visibly. The helper's default model label is `protenix_base_default_v1.0.0`; JSON output does not independently identify the checkpoint, so retain the prediction run's metadata.

Expected seed/sample checks apply to each **observed** job. A wholly absent job is not discoverable from confidence files; compare the job list against the input JSON. ipTM is model confidence in interfaces, not measured accuracy against an experimental structure. A benchmark needs its own reference structures and evaluation metrics.

## Maintaining the image

The dependency lock targets the container platform, not the maintainer's Mac. Regenerate deliberately from the repository root, review changes and rerun CI:

```bash
uv pip compile protenix/requirements.in \
    --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
    --generate-hashes --output-file protenix/requirements.lock
python3 -m unittest discover -s protenix -p 'test*.py' -v
```

Do not change the source pin, checkpoint selection or inference settings without recording the change. Updating host launchers or documentation does not require regenerating model assets.

## Sources and licence

- [Protenix 1.0.9 source](https://github.com/bytedance/Protenix/tree/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d), including the model configuration and output writer inspected for this installation.
- [Model configuration](https://github.com/bytedance/Protenix/blob/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d/configs/configs_model_type.py): distinguishes the v1 default checkpoint from the later-data-cutoff checkpoint.
- [Upstream inference instructions](https://github.com/bytedance/Protenix/blob/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d/docs/infer_json_format.md) and [licence](https://github.com/bytedance/Protenix/blob/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d/LICENSE).

The selected v1 source and model are distributed under upstream's Apache 2.0 terms. Follow any separate terms for input datasets and external resources used in an analysis.
