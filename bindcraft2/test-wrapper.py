#!/usr/bin/env python3
"""Exercise host launcher routing with a recording Apptainer stub; no GPU needed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bindcraft wrapper ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.install = self.root / "software install"
        self.weights = self.install / "weights/alphafold"
        self.weights.mkdir(parents=True)
        self.sif = self.install / "bindcraft2.sif"
        self.sif.write_text("existing image placeholder\n")
        subprocess.run(["bash", str(SOURCE / "install-launcher.sh"), str(self.install)],
                       check=True, capture_output=True, text=True)
        self.assertEqual(self.sif.read_text(), "existing image placeholder\n")
        self.launcher = self.install / "bin/bindcraft"
        self.assertTrue(os.access(self.launcher, os.X_OK))
        self.assertTrue((self.install / "examples/run-wrapper.slurm").is_file())
        fake_bin = self.root / "fake bin"
        fake_bin.mkdir()
        fake = fake_bin / "apptainer"
        fake.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as handle:
    handle.write(json.dumps({"args": sys.argv[1:], "env": {
        k.removeprefix("APPTAINERENV_"): v for k, v in os.environ.items()
        if k.startswith("APPTAINERENV_")}}) + "\\n")
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
''')
        fake.chmod(0o755)
        self.log = self.root / "calls.jsonl"
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("APPTAINER", "BINDCRAFT", "SLURM", "CUDA_", "FAKE_"))}
        self.env.update(PATH=f"{fake_bin}:{os.environ['PATH']}", FAKE_LOG=str(self.log),
                        BINDCRAFT_SCRATCH_ROOT=str(self.root / "scratch with spaces"))

    def invoke(self, *arguments, **environment):
        result = subprocess.run([str(self.launcher), *arguments], cwd=self.root,
                                env={**self.env, **environment}, capture_output=True, text=True)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        for call in calls:
            self.assertFalse(Path(call["env"]["TMPDIR"]).exists(), "Temporary directory leaked")
        return result, calls

    def test_help_and_listing_without_gpu(self):
        for arguments in ((), ("--help",), ("design", "--help"), ("design", "--list-targets")):
            with self.subTest(arguments=arguments):
                result, calls = self.invoke(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                call = calls[-1]
                self.assertNotIn("--nv", call["args"])
                self.assertEqual(call["env"]["JAX_PLATFORMS"], "cpu")
                self.assertEqual(call["env"]["CUDA_VISIBLE_DEVICES"], "")
                self.assertTrue(Path(call["env"]["MPLCONFIGDIR"]).is_dir())

    def test_design_refuses_no_allocation_even_if_gpu_variable_is_set(self):
        result, calls = self.invoke("design", "settings.json", CUDA_VISIBLE_DEVICES="0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Slurm GPU allocation", result.stderr)
        self.assertEqual(calls, [])

    def test_gpu_allocation_requires_visible_devices(self):
        for devices in ("", "-1", "NoDevFiles", "none", "void"):
            with self.subTest(devices=devices):
                result, calls = self.invoke("--check-gpu", SLURM_JOB_ID="123", CUDA_VISIBLE_DEVICES=devices)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])

    def test_gpu_design_preserves_arguments_devices_and_paths(self):
        arguments = ("design", "settings with spaces.json", "--set", "hotspots=A:1,2",
                     "--set", "project_folder=results/literal $(value)")
        result, calls = self.invoke(*arguments, SLURM_JOB_ID="123", CUDA_VISIBLE_DEVICES="0,2",
                                    SLURM_CPUS_PER_TASK="4")
        self.assertEqual(result.returncode, 0, result.stderr)
        call, = calls
        self.assertIn("--nv", call["args"])
        self.assertIn("--no-eval", call["args"])
        index = call["args"].index(str(self.sif))
        self.assertEqual(call["args"][index + 1:], ["bindcraft", *arguments])
        self.assertEqual(call["args"][call["args"].index("--pwd") + 1], str(self.root))
        self.assertEqual(call["env"]["CUDA_VISIBLE_DEVICES"], "0,2")
        self.assertEqual(call["env"]["JAX_PLATFORMS"], "cuda")
        self.assertEqual(call["env"]["BINDCRAFT_AF2_PARAMS"], str(self.weights))
        self.assertEqual(call["env"]["OMP_NUM_THREADS"], "4")
        self.assertEqual(call["env"]["BINDCRAFT_WORKERS_PER_GPU"], "1")

    def test_installation_check_stays_on_cpu_and_checks_external_weights(self):
        result, calls = self.invoke("--check-install", SLURM_JOB_ID="123", CUDA_VISIBLE_DEVICES="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["args"][-1], "bindcraft2-smoke-test")
        self.assertEqual(calls[1]["args"][-4:], ["python", "-m", "bindcraft.selfcheck", "cuda12"])
        self.assertTrue(all(call["env"]["JAX_PLATFORMS"] == "cpu" for call in calls))

    def test_gpu_check_runs_selfcheck_and_cuda_computation(self):
        result, calls = self.invoke("--check-gpu", SLURM_JOB_ID="123", CUDA_VISIBLE_DEVICES="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertIn("bindcraft.selfcheck", calls[0]["args"])
        self.assertIn("jax.jit", calls[1]["args"][-1])
        self.assertTrue(all(call["env"]["JAX_PLATFORMS"] == "cuda" for call in calls))

    def test_failures_propagate_and_stop_checks(self):
        result, calls = self.invoke("--check-install", FAKE_EXIT="37")
        self.assertEqual(result.returncode, 37)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("PASS", result.stdout)

    def test_missing_weights_stop_installation_check(self):
        self.weights.rmdir()
        result, calls = self.invoke("--check-install")
        self.assertEqual(result.returncode, 2)
        self.assertIn("AlphaFold parameter directory", result.stderr)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
