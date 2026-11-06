#!/opt/venv/bin/python
"""Offline CPU installation checks; no checkpoint or scientific prediction."""

import ctypes
import importlib
from importlib import metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def main():
    # Keep all runtime writes inside this process's disposable writable folder.
    # The surrounding CI run disables the network and makes the image read-only.
    with tempfile.TemporaryDirectory(prefix="protenix-smoke-") as temp:
        for key, subdir in (
            ("PROTENIX_ROOT_DIR", "assets"),
            ("MPLCONFIGDIR", "matplotlib"),
            ("XDG_CACHE_HOME", "cache"),
            ("TORCH_HOME", "torch"),
            ("TORCH_EXTENSIONS_DIR", "torch-extensions"),
            ("TRITON_CACHE_DIR", "triton"),
        ):
            os.environ[key] = str(Path(temp) / subdir)
        os.environ["LAYERNORM_TYPE"] = "torch"
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        os.environ["OMP_NUM_THREADS"] = "1"

        command(sys.executable, "-m", "pip", "check")
        assert metadata.version("protenix") == "1.0.9"
        for module in (
            "numpy", "scipy", "pandas", "rdkit.Chem", "biotite",
            "Bio", "modelcif", "gemmi", "pdbeccdutils", "esm",
            "sklearn.neighbors", "optree", "runner.batch_inference",
            "runner.inference", "runner.dumper",
            "protenix.data.inference.json_parser",
            "protenix.data.inference.infer_dataloader",
            "protenix.data.core.featurizer", "protenix.model.protenix",
        ):
            importlib.import_module(module)

        import numpy as np
        import torch
        from rdkit import Chem
        from configs.configs_model_type import model_configs
        from protenix.model.triangular.layers import Attention, LayerNorm
        from protenix.model.triangular.triangular import (
            TriangleMultiplicationIncoming,
            TriangleMultiplicationOutgoing,
        )
        from protenix.web_service.dependency_url import URL

        assert torch.__version__.split("+")[0] == "2.7.1"
        assert torch.version.cuda == "12.6", torch.version.cuda
        assert not torch.cuda.is_available(), "Smoke test must run on CPU"
        assert torch.backends.cuda.is_built()
        # Unlike get_arch_list(), this compile-time query also works without a GPU.
        assert "sm_80" in torch._C._cuda_getArchFlags(), "A100 support missing"
        for package, relative in (
            ("nvidia-cuda-runtime-cu12", "nvidia/cuda_runtime/lib/libcudart.so.12"),
            ("nvidia-cublas-cu12", "nvidia/cublas/lib/libcublas.so.12"),
            ("nvidia-cudnn-cu12", "nvidia/cudnn/lib/libcudnn.so.9"),
        ):
            path = Path(metadata.distribution(package).locate_file(relative))
            assert path.is_file(), path
            ctypes.CDLL(str(path))

        model = "protenix_base_default_v1.0.0"
        assert model_configs[model]["model"]["N_cycle"] == 10
        assert model_configs[model]["sample_diffusion"]["N_step"] == 200
        assert URL[model].endswith(f"/{model}.pt")
        assert "protenix-v2" not in model_configs

        # Exercise the same native Torch kernels selected by the HPC wrapper.
        torch.manual_seed(7)
        torch.set_num_threads(1)
        with torch.inference_mode():
            tensor = torch.randn(2, 5, 8)
            normalized = LayerNorm(8)(tensor)
            np.testing.assert_allclose(normalized.mean(-1).numpy(), 0, atol=1e-5)
            attn = Attention(c_q=8, c_k=8, c_v=8, c_hidden=4, no_heads=2)
            result = attn(tensor, tensor, triangle_attention="torch")
            assert result.shape == tensor.shape and torch.isfinite(result).all()
            pair = torch.randn(5, 5, 8)
            mask = torch.ones(5, 5)
            for cls in (TriangleMultiplicationIncoming, TriangleMultiplicationOutgoing):
                result = cls(c_z=8, c_hidden=8)(
                    pair, mask=mask, triangle_multiplicative="torch"
                )
                assert result.shape == pair.shape and torch.isfinite(result).all()
        molecule = Chem.MolFromSmiles("CCO")
        assert molecule is not None and molecule.GetNumAtoms() == 3
        assert "Usage:" in command("protenix", "--help")
        prediction_help = command("protenix", "pred", "--help")
        assert "--model_name" in prediction_help and "--triatt_kernel" in prediction_help
        assert "--help" in command("protenix-assets", "--help")
        assert "--help" in command("protenix-predict", "--help")
        assert "--help" in command("protenix-summarize", "--help")

        # Nothing in a startup/import test should fetch model data implicitly.
        assert not list((Path(temp) / "assets").rglob("*.pt"))
        print("PASS: Protenix 1.0.9, exact v1 model config, inference imports, "
              "native Torch CPU kernels, CUDA 12.6 libraries/A100 build support, "
              "RDKit and CLI startup; no checkpoint or GPU prediction performed")


if __name__ == "__main__":
    main()
