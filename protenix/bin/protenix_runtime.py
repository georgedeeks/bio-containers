"""Offline runtime for Protenix v1.0.9, upstream commit 510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d.

Local SHA256 records detect later corruption, not upstream authenticity.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import urllib.request

MODEL = "protenix_base_default_v1.0.0"
VERSION = "1.0.9"
SOURCE_COMMIT = "510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d"
ORIGIN = "https://protenix.tos-cn-beijing.volces.com/"
ASSETS = {name: ORIGIN + name for name in (
    f"checkpoint/{MODEL}.pt", "common/components.cif",
    "common/components.cif.rdkit_mol.pkl", "common/clusters-by-entity-40.txt",
    "common/obsolete_release_date.csv",
)}
MANIFEST = "protenix-assets.json"
SMOKE_INPUT = [{"name": "installation_smoke", "sequences": [{"proteinChain": {
    "sequence": "ACDEFGHIKLMNPQRSTVWY", "count": 2,
}}]}]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("w") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def absolute_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"Use an absolute path: {value}")
    return path.resolve()


def read_manifest(root):
    path = root / MANIFEST
    if not path.is_file():
        raise ValueError(f"Missing {path}; run protenix-assets download on software23 first")
    manifest = json.loads(path.read_text())
    if manifest.get("model") != MODEL or manifest.get("source_version") != VERSION:
        raise ValueError(f"Asset manifest is for a different model or code version: {path}")
    if not isinstance(manifest.get("files"), dict):
        raise ValueError(f"Invalid asset manifest: {path}")
    return manifest


def check_asset(root, relative, record, full=True):
    path = root / relative
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty asset: {path}")
    if (record.get("url") != ASSETS[relative]
            or record.get("size") != path.stat().st_size
            or not re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", ""))):
        raise ValueError(f"Asset does not match its manifest: {path}")
    if full and sha256(path) != record["sha256"]:
        raise ValueError(f"Asset checksum mismatch: {path}")


def check_assets(root, full=True):
    manifest = read_manifest(root)
    if set(manifest["files"]) != set(ASSETS):
        raise ValueError("Asset staging is incomplete; rerun protenix-assets download on software23")
    for relative in ASSETS:
        check_asset(root, relative, manifest["files"][relative], full=full)
    return manifest


def download_assets(root):
    root.mkdir(parents=True, exist_ok=True)
    # flock prevents concurrent writers without stale lock-file removal.
    with (root / ".protenix-download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = read_manifest(root) if (root / MANIFEST).exists() else {
            "model": MODEL, "source_version": VERSION, "source_commit": SOURCE_COMMIT,
            "checksum_scope": "Local download integrity; not upstream-authenticated checksums", "files": {},
        }
        for relative, url in ASSETS.items():
            target = root / relative
            if relative in manifest["files"]:
                check_asset(root, relative, manifest["files"][relative])
                print(f"Verified existing {relative}", flush=True)
                continue
            if target.exists():
                raise ValueError(f"Unrecorded asset already exists: {target}; use a new staging directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            print(f"Downloading {url} -> {target}", flush=True)
            request = urllib.request.Request(url, headers={"User-Agent": "bio-containers-protenix-v1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError(f"Refusing a non-HTTPS redirect for {url}")
                if response.headers.get_content_type() in ("text/html", "application/xml", "text/xml"):
                    raise ValueError(f"Server returned a webpage instead of an asset: {url}")
                expected_size = response.headers.get("Content-Length")
                digest, size = hashlib.sha256(), 0
                with partial.open("wb") as handle:
                    while block := response.read(8 * 1024 * 1024):
                        handle.write(block)
                        digest.update(block)
                        size += len(block)
                    handle.flush()
                    os.fsync(handle.fileno())
                if size == 0 or (expected_size is not None and size != int(expected_size)):
                    raise ValueError(f"Incomplete download for {relative}; partial retained for diagnosis")
            partial.replace(target)
            manifest["files"][relative] = {
                "url": url, "size": size, "sha256": digest.hexdigest(),
                "downloaded_utc": datetime.now(timezone.utc).isoformat(),
            }
            write_json(root / MANIFEST, manifest)
        check_assets(root)
    print(f"PASS: all {MODEL} assets staged and checksummed at {root}")


def assets_main(argv=None):
    parser = argparse.ArgumentParser(description=f"Stage/check offline assets for {MODEL}; no inference")
    parser.add_argument("action", choices=("download", "check"))
    parser.add_argument("--root", required=True, help="Absolute persistent asset directory")
    args = parser.parse_args(argv)
    root = absolute_path(args.root)
    if args.action == "download":
        download_assets(root)
    else:
        check_assets(root)
        print(f"PASS: full SHA256 integrity check for {MODEL}")


def parse_seeds(value):
    if not re.fullmatch(r"\d+(,\d+)*", value):
        raise argparse.ArgumentTypeError("Seeds must be comma-separated non-negative integers")
    seeds = [int(item) for item in value.split(",")]
    if len(set(seeds)) != len(seeds) or any(seed >= 2**32 for seed in seeds):
        raise argparse.ArgumentTypeError("Seeds must be unique and less than 2^32")
    return seeds


def validate_input(path, no_msa=False):
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise ValueError("Input must be a non-empty Protenix JSON list, not AlphaFold JSON")
    names = set()
    for job in data:
        if not isinstance(job, dict):
            raise ValueError("Every input job must be an object")
        name = job.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name in names:
            raise ValueError(f"Job names must be unique safe filenames: {name!r}")
        names.add(name)
        if "modelSeeds" in job:
            raise ValueError("Pass seeds explicitly with --seeds; remove modelSeeds from input JSON")
        sequences = job.get("sequences")
        if not isinstance(sequences, list) or not sequences:
            raise ValueError(f"Job {name} has no sequences")
        for entity in sequences:
            if not isinstance(entity, dict) or len(entity) != 1:
                raise ValueError(f"Invalid entity in {name}")
            kind, chain = next(iter(entity.items()))
            if not isinstance(chain, dict):
                raise ValueError(f"Invalid entity data in {name}")
            count = chain.get("count", 1)
            if type(count) is not int or count < 1:
                raise ValueError(f"Invalid entity count in {name}")
            if chain.get("templatesPath") or chain.get("rna_msa_path"):
                raise ValueError("This runner does not enable templates or RNA MSA; remove those fields")
            if kind == "proteinChain":
                sequence = chain.get("sequence", "")
                if not isinstance(sequence, str) or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYX]+", sequence):
                    raise ValueError(f"Invalid or empty protein sequence in {name}")
                if "msa" in chain:
                    raise ValueError("Convert legacy msa entries to pairedMsaPath/unpairedMsaPath first")
                paths = [chain.get(key) for key in ("pairedMsaPath", "unpairedMsaPath")]
                if not no_msa and not any(value is not None for value in paths):
                    raise ValueError(f"Missing precomputed MSA in {name}; use --no-msa only intentionally")
                for value in paths:
                    if value is not None:
                        alignment = absolute_path(value)
                        if not alignment.is_file() or alignment.stat().st_size == 0:
                            raise ValueError(f"Missing/empty precomputed MSA: {alignment}")
            elif kind == "ligand" and str(chain.get("ligand", "")).startswith("FILE_"):
                ligand = absolute_path(chain["ligand"][5:])
                if not ligand.is_file():
                    raise ValueError(f"Missing ligand file: {ligand}")
            elif kind == "rnaSequence":
                raise ValueError("RNA input is outside this protein/ligand runner; RNA MSA is not enabled")
            elif kind not in ("ligand", "ion", "dnaSequence"):
                raise ValueError(f"Unsupported input entity: {kind}")
    return data


def referenced_input_files(jobs):
    """Fingerprint external alignments/ligands without modifying their contents."""
    records = {}
    for job in jobs:
        for entity_index, entity in enumerate(job["sequences"], start=1):
            kind, chain = next(iter(entity.items()))
            paths = {}
            if kind == "proteinChain":
                paths = {key: chain[key] for key in ("pairedMsaPath", "unpairedMsaPath")
                         if chain.get(key) is not None}
            elif kind == "ligand" and str(chain.get("ligand", "")).startswith("FILE_"):
                paths = {"ligand": chain["ligand"][5:]}
            for field, value in paths.items():
                path = absolute_path(value)
                resolved = str(path)
                if resolved not in records:
                    before = path.stat()
                    digest = sha256(path)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError(f"Input file changed while hashing: {path}")
                    records[resolved] = {
                        "path": resolved, "size": after.st_size, "sha256": digest, "references": [],
                    }
                records[resolved]["references"].append({
                    "job": job["name"], "entity": entity_index, "field": field, "input_path": value,
                })
    return list(records.values())


def verify_outputs(root, jobs, seeds, samples):
    errors = [str(p) for p in (root / "ERR").rglob("*") if p.is_file()]
    if errors:
        raise ValueError("Protenix reported errors: " + ", ".join(errors))
    for job in jobs:
        for seed in seeds:
            directory = root / job["name"] / f"seed_{seed}" / "predictions"
            for sample in range(samples):
                prefix = job["name"]
                cif = directory / f"{prefix}_sample_{sample}.cif"
                confidence = directory / f"{prefix}_summary_confidence_sample_{sample}.json"
                if not cif.is_file() or cif.stat().st_size == 0 or not confidence.is_file():
                    raise ValueError(f"Missing prediction for {prefix}, seed {seed}, sample {sample}")
                scores = json.loads(confidence.read_text())
                for field in ("ptm", "iptm", "plddt", "ranking_score"):
                    value = scores.get(field)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError(f"Invalid {field} in {confidence}")


def deny_network(event, args):
    if event in ("socket.connect", "socket.sendto") and args[0].family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError("Network disabled during inference; precompute MSAs and stage assets on software23")


def run_upstream(arguments, cpu_smoke=False):
    if metadata.version("protenix") != VERSION:
        raise RuntimeError(f"This runner requires Protenix {VERSION}")
    if cpu_smoke:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sys.addaudithook(deny_network)
    import torch
    if not cpu_smoke and not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU available; run inside a Slurm GPU allocation with apptainer --nv")
    if cpu_smoke:
        print("CPU installation smoke only: synthetic input, one cycle/step/sample; no scientific validation")
    else:
        print(f"GPU: {torch.cuda.get_device_name(0)}; Torch {torch.__version__}; CUDA {torch.version.cuda}")
    from runner.batch_inference import protenix_cli
    protenix_cli.main(args=arguments, standalone_mode=False)


def predict_main(argv=None):
    parser = argparse.ArgumentParser(description=f"Offline, fixed-model prediction with {MODEL}")
    parser.add_argument("--assets", required=True)
    parser.add_argument("--input", required=True, help="Absolute Protenix JSON path")
    parser.add_argument("--out-dir", required=True, help="New absolute output directory; never overwritten")
    parser.add_argument("--seeds", type=parse_seeds, default=parse_seeds("101"))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--no-msa", action="store_true", help="Explicit MSA-free run; not equivalent to an MSA-backed benchmark")
    parser.add_argument("--dtype", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--cpu-smoke-test", action="store_true", help="Bundled synthetic input only; forces one seed/sample/cycle/step, fp32 and no MSA")
    args = parser.parse_args(argv)
    if args.samples < 1:
        raise ValueError("--samples must be positive")
    if args.cpu_smoke_test:
        args.no_msa, args.dtype, args.seeds, args.samples = True, "fp32", [101], 1
    assets, source, output = map(absolute_path, (args.assets, args.input, args.out_dir))
    asset_manifest = check_assets(assets, full=False)  # Full check once after staging/copying.
    jobs = validate_input(source, args.no_msa)
    if args.cpu_smoke_test and jobs != SMOKE_INPUT:
        raise ValueError("--cpu-smoke-test accepts only the bundled example-smoke.json synthetic homodimer")
    if output.exists():
        raise ValueError(f"Output already exists; choose a fresh directory: {output}")
    external_inputs = referenced_input_files(jobs)
    output.mkdir(parents=True)
    manifest_copy = output / MANIFEST
    write_json(manifest_copy, asset_manifest)
    # Keep upstream preprocessing away from the user's original input.
    input_copy = output / "input.json"
    write_json(input_copy, jobs)
    os.environ["PROTENIX_ROOT_DIR"] = str(assets)
    os.environ["LAYERNORM_TYPE"] = "torch"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    cycle, step = (1, 1) if args.cpu_smoke_test else (10, 200)
    arguments = [
        "pred", "--input", str(input_copy), "--out_dir", str(output),
        "--model_name", MODEL, "--seeds", ",".join(map(str, args.seeds)),
        "--sample", str(args.samples), "--cycle", str(cycle), "--step", str(step),
        "--use_default_params", "false",
        "--dtype", args.dtype, "--use_msa", str(not args.no_msa).lower(),
        "--use_template", "false", "--use_rna_msa", "false", "--use_seeds_in_json", "false",
        "--trimul_kernel", "torch", "--triatt_kernel", "torch",
        "--enable_cache", "true", "--enable_fusion", "false",
    ]
    record = {
        "model": MODEL, "source_version": VERSION, "source_commit": SOURCE_COMMIT,
        "input_sha256": sha256(source), "asset_manifest_sha256": sha256(manifest_copy),
        "asset_manifest_file": MANIFEST, "external_input_files": external_inputs,
        "seeds": args.seeds, "samples_per_seed": args.samples, "dtype": args.dtype,
        "msa": not args.no_msa, "protenix_arguments": arguments,
        "cpu_installation_smoke": args.cpu_smoke_test,
        "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
    }
    write_json(output / "run-info.json", record)
    try:
        run_upstream(arguments, cpu_smoke=args.cpu_smoke_test)
        verify_outputs(output, jobs, args.seeds, args.samples)
    except BaseException as exc:
        record.update(status="failed", error=str(exc))
        write_json(output / "run-info.json", record)
        raise
    record.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(output / "run-info.json", record)
    print(f"PASS: complete CIF/confidence outputs for {len(jobs)} jobs × {len(args.seeds)} seeds × {args.samples} samples")


def command(main):
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
