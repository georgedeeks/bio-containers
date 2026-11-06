"""Synthetic fixtures test aggregation and validation, not biological accuracy."""

import contextlib
import csv
import importlib.util
import io
import json
import math
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "confidence_summary", Path(__file__).with_name("summarize-confidence.py")
)
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "outputs"
        self.root.mkdir()

    def fixture(self, job, seed, values):
        directory = self.root / job / f"seed_{seed}" / "predictions"
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for sample, value in enumerate(values):
            path = directory / f"{Path(job).name}_summary_confidence_sample_{sample}.json"
            path.write_text(json.dumps({"iptm": value, "ptm": 0.7, "ranking_score": value}))
            paths.append(path)
        return paths

    def test_equal_weight_seeds_and_sample_sd_with_unequal_sample_counts(self):
        self.fixture("complex", 101, [0.4])
        self.fixture("complex", 102, [0.7, 0.8, 0.9])
        seeds, jobs = summary.summarize(summary.read_samples(self.root))
        self.assertEqual([row["n_samples"] for row in seeds], [1, 3])
        self.assertAlmostEqual(jobs[0]["iptm_mean_of_seed_means"], 0.6)
        self.assertAlmostEqual(jobs[0]["iptm_across_seed_sample_sd"], math.sqrt(0.08))
        self.assertEqual(jobs[0]["n_seeds"], 2)
        self.assertEqual(jobs[0]["n_samples"], 4)
        self.assertIsNone(seeds[0]["iptm_within_seed_sample_sd"])

    def test_multiple_jobs_and_single_seed_sd_is_unavailable(self):
        self.fixture("batch-a/complex", 5, [0.2, 0.4])
        self.fixture("batch-b/complex", 5, [0.9])
        _, jobs = summary.summarize(summary.read_samples(self.root))
        self.assertEqual([row["job"] for row in jobs], ["batch-a/complex", "batch-b/complex"])
        self.assertAlmostEqual(jobs[0]["iptm_mean_of_seed_means"], 0.3)
        self.assertIsNone(jobs[0]["iptm_across_seed_sample_sd"])

    def test_expected_seeds_and_samples_detect_incomplete_outputs(self):
        self.fixture("complex", 101, [0.4, 0.5])
        rows = summary.read_samples(self.root)
        with self.assertRaisesRegex(ValueError, "expected seeds"):
            summary.summarize(rows, expected_seeds=[101, 102])
        with self.assertRaisesRegex(ValueError, "expected sample labels"):
            summary.summarize(rows, expected_samples=3)
        summary.summarize(rows, expected_seeds=[101], expected_samples=2)

    def test_invalid_iptm_fails_instead_of_silently_dropping_sample(self):
        paths = self.fixture("complex", 101, [0.4])
        for data in ({}, {"iptm": "0.5"}, {"iptm": True}, {"iptm": None},
                     {"iptm": float("nan")}, {"iptm": 1.2}, []):
            with self.subTest(data=data):
                paths[0].write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    summary.read_samples(self.root)

    def test_no_results_and_wrong_layout_fail(self):
        with self.assertRaisesRegex(ValueError, "No Protenix"):
            summary.read_samples(self.root)
        path = self.root / "complex_summary_confidence_sample_0.json"
        path.write_text('{"iptm": 0.5}')
        with self.assertRaisesRegex(ValueError, "Unexpected Protenix output layout"):
            summary.read_samples(self.root)

    def test_duplicate_numeric_sample_labels_fail(self):
        paths = self.fixture("complex", 101, [0.4])
        duplicate = paths[0].with_name("complex_summary_confidence_sample_00.json")
        duplicate.write_text(paths[0].read_text())
        with self.assertRaisesRegex(ValueError, "Duplicate job/seed/sample"):
            summary.read_samples(self.root)

    def test_cli_writes_auditable_rows_and_does_not_overwrite(self):
        self.fixture("complex", 101, [0.4, 0.6])
        reports = self.root.parent / "reports"
        args = [str(self.root), "--output-dir", str(reports),
                "--expected-seeds", "101", "--expected-samples", "2"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(args), 0)
        with (reports / "per_sample.csv").open() as handle:
            samples = list(csv.DictReader(handle))
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[1]["sample"], "1")
        self.assertTrue((self.root / samples[1]["source_json"]).is_file())
        with (reports / "across_seeds.csv").open() as handle:
            job = next(csv.DictReader(handle))
        self.assertEqual(job["iptm_across_seed_sample_sd"], "")
        metadata = json.loads((reports / "summary.json").read_text())
        self.assertIsNone(metadata["jobs"][0]["iptm_across_seed_sample_sd"])
        original = (reports / "summary.json").read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            summary.main(args)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual((reports / "summary.json").read_bytes(), original)

    def test_failed_completeness_check_writes_no_report(self):
        self.fixture("complex", 101, [0.4])
        reports = self.root.parent / "reports"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            summary.main([str(self.root), "--output-dir", str(reports),
                          "--expected-seeds", "101,102"])
        self.assertFalse(reports.exists())


if __name__ == "__main__":
    unittest.main()
