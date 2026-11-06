"""Failure-focused offline tests: no Protenix installation, GPU or network required."""
from copy import deepcopy
from contextlib import redirect_stdout
from email.message import Message
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "bin"))
import protenix_runtime as runtime


class Response(io.BytesIO):
    def __init__(self, data, size=None):
        super().__init__(data)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(data) if size is None else size)
        self.headers["Content-Type"] = "application/octet-stream"

    def geturl(self):
        return runtime.ORIGIN + "asset"


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.input = self.root / "input.json"
        self.output = self.root / "result"
        self.input.write_text(json.dumps(runtime.SMOKE_INPUT))
        self.capture = redirect_stdout(io.StringIO())
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)
        self.environment = patch.dict(runtime.os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def stage_assets(self):
        with patch.object(runtime.urllib.request, "urlopen", side_effect=lambda *_a, **_k: Response(b"test asset")):
            runtime.download_assets(self.assets)

    def args(self, *extra):
        return ["--assets", str(self.assets), "--input", str(self.input),
                "--out-dir", str(self.output), "--seeds", "101", "--samples", "1", *extra]

    def make_outputs(self, *_args, **_kwargs):
        out = self.output / "installation_smoke" / "seed_101" / "predictions"
        out.mkdir(parents=True)
        (out / "installation_smoke_sample_0.cif").write_text("data_test\n")
        (out / "installation_smoke_summary_confidence_sample_0.json").write_text(
            json.dumps({"ptm": 0.3, "iptm": 0.2, "plddt": 30.0, "ranking_score": 0.22}))

    def test_download_restart_reuses_verified_completed_files(self):
        self.stage_assets()
        with patch.object(runtime.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")):
            runtime.download_assets(self.assets)
        self.assertEqual(set(runtime.check_assets(self.assets)["files"]), set(runtime.ASSETS))

    def test_truncated_download_never_publishes_complete_asset(self):
        with patch.object(runtime.urllib.request, "urlopen", return_value=Response(b"partial", size=100)):
            with self.assertRaisesRegex(ValueError, "Incomplete download"):
                runtime.download_assets(self.assets)
        relative = next(iter(runtime.ASSETS))
        self.assertFalse((self.assets / relative).exists())
        self.assertTrue((self.assets / (relative + ".partial")).exists())

    def test_corruption_fails_full_checksum_check(self):
        self.stage_assets()
        target = self.assets / next(iter(runtime.ASSETS))
        target.write_bytes(b"bad! asset")  # Same byte length; a size check alone would miss this.
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            runtime.check_assets(self.assets)

    def test_missing_msa_rejected_before_upstream_can_search(self):
        self.stage_assets()
        with patch.object(runtime, "run_upstream") as upstream:
            with self.assertRaisesRegex(ValueError, "Missing precomputed MSA"):
                runtime.predict_main(self.args())
            upstream.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_precomputed_absolute_msa_is_accepted(self):
        msa = self.root / "alignment.a3m"
        msa.write_text(">query\nACDEFGHIKLMNPQRSTVWY\n")
        data = deepcopy(runtime.SMOKE_INPUT)
        data[0]["sequences"][0]["proteinChain"]["unpairedMsaPath"] = str(msa)
        self.input.write_text(json.dumps(data))
        self.assertEqual(runtime.validate_input(self.input), data)
        msa.write_text("")
        with self.assertRaisesRegex(ValueError, "Missing/empty"):
            runtime.validate_input(self.input)

    def test_unsafe_or_duplicate_job_names_are_rejected(self):
        for jobs in ([{**runtime.SMOKE_INPUT[0], "name": "../escape"}], runtime.SMOKE_INPUT * 2):
            self.input.write_text(json.dumps(jobs))
            with self.assertRaisesRegex(ValueError, "unique safe filenames"):
                runtime.validate_input(self.input, no_msa=True)

    def test_exit_zero_without_outputs_is_failure(self):
        self.stage_assets()
        with patch.object(runtime, "run_upstream", return_value=None):
            with self.assertRaisesRegex(ValueError, "Missing prediction"):
                runtime.predict_main(self.args("--no-msa"))
        self.assertEqual(json.loads((self.output / "run-info.json").read_text())["status"], "failed")

    def test_upstream_error_files_fail_even_with_outputs(self):
        self.make_outputs()
        (self.output / "ERR").mkdir()
        (self.output / "ERR" / "job.txt").write_text("CUDA out of memory")
        with self.assertRaisesRegex(ValueError, "Protenix reported errors"):
            runtime.verify_outputs(self.output, runtime.SMOKE_INPUT, [101], 1)

    def test_missing_seed_or_sample_is_failure(self):
        self.make_outputs()
        for seeds, samples in (([101, 102], 1), ([101], 2)):
            with self.assertRaisesRegex(ValueError, "Missing prediction"):
                runtime.verify_outputs(self.output, runtime.SMOKE_INPUT, seeds, samples)

    def test_success_records_fixed_model_and_preserves_original_input(self):
        self.stage_assets()
        original = self.input.read_bytes()
        with patch.object(runtime, "run_upstream", side_effect=self.make_outputs) as upstream:
            runtime.predict_main(self.args("--no-msa"))
        self.assertEqual(self.input.read_bytes(), original)
        record = json.loads((self.output / "run-info.json").read_text())
        self.assertEqual(record["status"], "complete")
        self.assertEqual(record["model"], "protenix_base_default_v1.0.0")
        arguments = upstream.call_args.args[0]
        self.assertEqual(arguments[arguments.index("--triatt_kernel") + 1], "torch")
        self.assertEqual(arguments[arguments.index("--enable_fusion") + 1], "false")
        with self.assertRaisesRegex(ValueError, "Output already exists"):
            runtime.predict_main(self.args("--no-msa"))

    def test_cpu_smoke_is_fixed_and_rejects_real_inputs(self):
        self.stage_assets()
        with patch.object(runtime, "run_upstream", side_effect=self.make_outputs) as upstream:
            runtime.predict_main(self.args("--cpu-smoke-test"))
        arguments = upstream.call_args.args[0]
        self.assertTrue(upstream.call_args.kwargs["cpu_smoke"])
        self.assertEqual(arguments[arguments.index("--cycle") + 1], "1")
        self.assertEqual(arguments[arguments.index("--dtype") + 1], "fp32")
        self.assertEqual(arguments[arguments.index("--use_default_params") + 1], "false")
        data = deepcopy(runtime.SMOKE_INPUT)
        data[0]["sequences"][0]["proteinChain"]["sequence"] = "ACDE"
        self.input.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "only the bundled"):
            runtime.predict_main(self.args("--cpu-smoke-test"))

    def test_network_guard_refuses_internet_allows_unix(self):
        class FakeSocket:
            family = socket.AF_INET
        with self.assertRaisesRegex(RuntimeError, "Network disabled"):
            runtime.deny_network("socket.connect", (FakeSocket(), ("example.com", 443)))
        FakeSocket.family = socket.AF_UNIX
        runtime.deny_network("socket.connect", (FakeSocket(), "/tmp/local.sock"))


if __name__ == "__main__":
    unittest.main()
