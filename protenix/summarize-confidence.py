#!/usr/bin/env python3
"""Summarize Protenix confidence without counting diffusion samples as seeds.

The layout follows runner/dumper.py at upstream commit
510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d (Protenix code v1.0.9).
Use one output tree per checkpoint/settings combination. The model-name field
is a caller-supplied label, not metadata inferred from confidence JSON.
"""

import argparse
import csv
import io
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path


MODEL_NAME = "protenix_base_default_v1.0.0"
FILE_PATTERN = re.compile(r"(?P<job>.+)_summary_confidence_sample_(?P<sample>\d+)\.json")
SEED_PATTERN = re.compile(r"seed_(\d+)")


def numeric_metric(data, key, path, required=False):
    value = data.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: {key} must be a numeric scalar")
    if not math.isfinite(value):
        raise ValueError(f"{path}: {key} must be finite")
    if key in ("iptm", "ptm") and not 0 <= value <= 1:
        raise ValueError(f"{path}: {key} must be in [0, 1]")
    return float(value)


def read_samples(root, model_name=MODEL_NAME):
    """Read the pinned writer's job/seed_N/predictions layout, failing loudly."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Output tree does not exist: {root}")
    paths = sorted(root.rglob("*_summary_confidence_*.json"))
    if not paths:
        raise ValueError(f"No Protenix summary confidence JSON files found under {root}")
    rows, seen = [], set()
    for path in paths:
        match = FILE_PATTERN.fullmatch(path.name)
        seed_dir = path.parent.parent
        seed_match = SEED_PATTERN.fullmatch(seed_dir.name)
        job_dir = seed_dir.parent
        if (match is None or seed_match is None or path.parent.name != "predictions"
                or match.group("job") != job_dir.name):
            raise ValueError(f"Unexpected Protenix output layout: {path}")
        job = job_dir.relative_to(root).as_posix()
        if job == ".":
            job = job_dir.name
        seed, sample = int(seed_match.group(1)), int(match.group("sample"))
        identity = (job, seed, sample)
        if identity in seen:
            raise ValueError(f"Duplicate job/seed/sample: {identity}")
        seen.add(identity)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object")
        rows.append({
            "model_name": model_name,
            "job": job,
            "seed": seed,
            "sample": sample,
            "iptm": numeric_metric(data, "iptm", path, required=True),
            "ptm": numeric_metric(data, "ptm", path),
            "ranking_score": numeric_metric(data, "ranking_score", path),
            "source_json": path.relative_to(root).as_posix(),
        })
    return sorted(rows, key=lambda row: (row["job"], row["seed"], row["sample"]))


def sample_sd(values):
    return statistics.stdev(values) if len(values) > 1 else None


def summarize(rows, expected_seeds=None, expected_samples=None):
    """Give each seed equal weight after averaging all its diffusion samples."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["model_name"], row["job"], row["seed"])].append(row)
    seed_rows, jobs = [], defaultdict(list)
    for (model, job, seed), members in sorted(grouped.items()):
        samples = {row["sample"] for row in members}
        if expected_samples is not None and samples != set(range(expected_samples)):
            raise ValueError(
                f"{job}, seed {seed}: expected sample labels 0..{expected_samples - 1}, "
                f"found {sorted(samples)}"
            )
        values = [row["iptm"] for row in members]
        row = {
            "model_name": model,
            "job": job,
            "seed": seed,
            "n_samples": len(values),
            "iptm_mean": statistics.mean(values),
            "iptm_within_seed_sample_sd": sample_sd(values),
        }
        seed_rows.append(row)
        jobs[(model, job)].append(row)
    job_rows = []
    for (model, job), members in sorted(jobs.items()):
        observed_seeds = {row["seed"] for row in members}
        if expected_seeds is not None and observed_seeds != set(expected_seeds):
            raise ValueError(
                f"{job}: expected seeds {sorted(expected_seeds)}, "
                f"found {sorted(observed_seeds)}"
            )
        means = [row["iptm_mean"] for row in members]
        job_rows.append({
            "model_name": model,
            "job": job,
            "n_seeds": len(means),
            "n_samples": sum(row["n_samples"] for row in members),
            "iptm_mean_of_seed_means": statistics.mean(means),
            "iptm_across_seed_sample_sd": sample_sd(means),
        })
    return seed_rows, job_rows


def csv_text(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def seed_list(value):
    try:
        seeds = [int(part) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use comma-separated nonnegative integer seeds") from exc
    if not seeds or min(seeds) < 0 or len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("Seeds must be distinct nonnegative integers")
    return seeds


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Must be at least 1")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_tree", type=Path, help="One Protenix run's output directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for new summary files")
    parser.add_argument("--model-name", default=MODEL_NAME, help="Checkpoint label, not inferred from files")
    parser.add_argument("--expected-seeds", type=seed_list, help="Require these exact seeds for every observed job")
    parser.add_argument("--expected-samples", type=positive_int, help="Require sample labels 0 through N-1 for every seed")
    args = parser.parse_args(argv)
    try:
        rows = read_samples(args.output_tree, args.model_name)
        seed_rows, job_rows = summarize(rows, args.expected_seeds, args.expected_samples)
        metadata = {
            "model_name": args.model_name,
            "source_directory": str(args.output_tree.resolve()),
            "expected_seeds": args.expected_seeds,
            "expected_samples_per_seed": args.expected_samples,
            "aggregation": "Arithmetic mean over diffusion samples within each seed; equal-weight arithmetic mean and sample SD (ddof=1) over seed means, separately for each job.",
            "sd_for_one_observation": "Unavailable: empty CSV cell / JSON null, not zero.",
            "sample_labels": "The pinned Protenix writer normally ranks sample filenames within each seed; sample 0 is not seed 0. No best-sample selection is performed.",
            "completeness": "Only observed jobs are summarized. Expected seed/sample checks do not detect a wholly absent job; compare against the input JSON and inspect Protenix ERR logs.",
            "jobs": job_rows,
        }
        reports = {
            "per_sample.csv": csv_text(rows),
            "per_seed.csv": csv_text(seed_rows),
            "across_seeds.csv": csv_text(job_rows),
            "summary.json": json.dumps(metadata, indent=2, allow_nan=False) + "\n",
        }
        for name in reports:
            if (args.output_dir / name).exists():
                raise ValueError(f"Refusing to overwrite {args.output_dir / name}; choose a new report directory")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in reports.items():
            with (args.output_dir / name).open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    for row in job_rows:
        sd = row["iptm_across_seed_sample_sd"]
        sd_text = f"{sd:.6f}" if sd is not None else "NA (one seed)"
        print(f"{row['job']}: ipTM {row['iptm_mean_of_seed_means']:.6f} ± {sd_text}; "
              f"{row['n_seeds']} seeds, {row['n_samples']} samples")
    print(f"Reports: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
