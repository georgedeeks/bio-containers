#!/opt/venv/bin/python
"""Offline installation checks; CPU execution is confined to this test process."""

import ctypes
import importlib
from importlib import metadata
import os
from pathlib import Path
import subprocess
import sys

os.environ["JAX_PLATFORMS"] = "cpu"
os.environ.setdefault("OMP_NUM_THREADS", "1")


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


command(sys.executable, "-m", "pip", "check")
for module in (
    "jax", "haiku", "optax", "biotite", "matplotlib", "numpy", "scipy",
    "ml_collections", "absl", "cuequivariance_jax", "bindcraft.proteinmpnn",
):
    importlib.import_module(module)

for package in ("jax-cuda12-plugin", "jax-cuda12-pjrt", "cuequivariance-ops-cu12"):
    print(f"{package}={metadata.version(package)}")
assert not any("cuda13" in dist.metadata["Name"].lower() or "-cu13" in dist.metadata["Name"].lower()
               for dist in metadata.distributions()), "Unexpected CUDA 13 package"

for library in ("libcudart.so.12", "libcublas.so.12", "libcudnn.so.9", "libcupti.so.12"):
    ctypes.CDLL(library)

import jax
import jax.numpy as jnp
import numpy as np
import bindcraft
from bindcraft.model_weights import DEFAULT_MPNN_MODEL, MPNN_WEIGHT_VARIANTS, SHIPPED_WEIGHTS
from bindcraft.proteinmpnn import read_mpnn_checkpoint
from bindcraft.settings import read_preset

array = np.arange(9, dtype=np.float32).reshape(3, 3)
actual = jax.jit(lambda x: x @ x.T)(jnp.asarray(array))
np.testing.assert_allclose(np.asarray(actual), array @ array.T)
assert jax.default_backend() == "cpu"

for directory in MPNN_WEIGHT_VARIANTS.values():
    checkpoint = SHIPPED_WEIGHTS / "proteinmpnn" / directory / f"{DEFAULT_MPNN_MODEL}.npz"
    parameters, num_edges = read_mpnn_checkpoint(str(checkpoint))
    assert parameters and num_edges > 0, f"Invalid ProteinMPNN checkpoint: {checkpoint}"

command(sys.executable, "-m", "bindcraft.selfcheck", "cuda12", "--shipped-only")
assert "usage:" in command("bindcraft", "--help")
assert "hPDL1" in command("bindcraft", "design", "--list-targets").splitlines()
assert "binder" in command("bindcraft", "design", "--list-modalities").splitlines()
source = Path(bindcraft.__file__).resolve().parent.parent
assert all(Path(target["target_path"]).is_file() for target in read_preset("target", "hPDL1")["targets"])
assert (source / "scaffolds").is_dir()
print(f"PASS: BindCraft2 {metadata.version('bindcraft')}; JAX {jax.__version__}; "
      "CPU JIT, CUDA libraries, packaged weights, presets and CLI startup")
