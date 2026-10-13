# AlphaFold 3.0.0: existing TSL installation

Evidence supplied by the user on 2026-10-13: the definition file, `module spider alphafold`, `module show alphafold/3.0.0`, and `Singularity.manifest`. The module and manifest both identify **AlphaFold 3.0.0**; the manifest embeds the supplied recipe and records a build by **RC on 2024-11-27 at 15:14:42 GMT**, using **Singularity 3.8.7-1.el9.centos**. The user reports successful AlphaFold use on the cluster over several years, including the earlier 2.x installations. This particular AF3 image was built on 2024-11-27, less than two years before this record; it should not be described as having several years of use. The module marks the image `Mutable: False` and exposes `run_alphafold.py` through a wrapper directory.

- Module file: `/nbi/software/modulefiles/sci/alphafold/3.0.0.lua`
- Image: `/nbi/software/containers/e8edb411-7374-4342-b9f1-408da41fc197/e8edb411-7374-4342-b9f1-408da41fc197.img`
- Wrapper directory: `/nbi/software/containers/e8edb411-7374-4342-b9f1-408da41fc197/bin`

The module inventory also advertises 2.0, 2.2.0, 2.3.1 and 2.3.2. The separate vault note `Code/Active/AlphaFold install 3.0.2.md` is not evidence that 3.0.2 was deployed; no 3.0.2 module appears in this listing. Model weights are not included in this deployment, according to the module and manifest.

| Component | Recipe and installed-package evidence |
| --- | --- |
| Base image | `nvidia/cuda:12.6.0-base-ubuntu22.04` |
| Python | **3.11.10**, checked by executing `/alphafold3_venv/bin/python --version`; installed from deadsnakes according to the recipe |
| HMMER | 3.4, compiled into `/hmmer` |
| AlphaFold | Installed package **`alphafold3==3.0.0`**, checked with pip. Source copied from `/tmp/pik23lik/alphafold3/`, installed under `/app/alphafold`; no commit/tag recorded in the recipe itself |
| JAX | **`jax==0.4.34`, `jaxlib==0.4.34`, `jax-cuda12-pjrt==0.4.34`, `jax-cuda12-plugin==0.4.34`**, checked with pip |
| CUDA Python packages | **`nvidia-cuda-runtime-cu12==12.6.77`, `nvidia-cuda-nvcc-cu12==12.6.77`, `nvidia-cublas-cu12==12.6.3.3`, `nvidia-cudnn-cu12==9.5.1.17`**, checked with pip; full list below |
| Other Python dependencies | Installed from the copied source tree's `dev-requirements.txt`, then `pip3 install --no-deps .`; observed versions recorded below |
| Runtime settings | Disables Triton GEMM and sets JAX/XLA memory-related variables; these are settings for this AF3 installation, not defaults to copy into other software |

**Evidence status:** the user reports that AlphaFold is an established working GPU application on this cluster. That operational history supports the container approach; the manifest establishes the age of this specific AF3 image. During this investigation the user also successfully executed Python and listed installed packages using `apptainer/1.4.5-2` and `--cleanenv`, without reserving a GPU. These checks document the installed stack; no repeat AlphaFold GPU test is needed for the container-planning task. Installed CUDA package versions describe the image's software; the host driver is recorded in the [cluster profile](../HPC_COMPATIBILITY.md).

<details>
<summary>Observed Python package inventory (2026-10-13)</summary>

Output of the pip inspection command below; an inventory of the existing image, not a proposed dependency set for new software:

```text
absl-py==2.1.0
alphafold3==3.0.0
chex==0.1.87
dm-haiku==0.0.13
dm-tree==0.1.8
filelock==3.16.1
jax==0.4.34
jax-cuda12-pjrt==0.4.34
jax-cuda12-plugin==0.4.34
jax-triton==0.2.0
jaxlib==0.4.34
jaxtyping==0.2.34
jmp==0.0.4
ml_dtypes==0.5.0
numpy==2.1.3
nvidia-cublas-cu12==12.6.3.3
nvidia-cuda-cupti-cu12==12.6.80
nvidia-cuda-nvcc-cu12==12.6.77
nvidia-cuda-runtime-cu12==12.6.77
nvidia-cudnn-cu12==9.5.1.17
nvidia-cufft-cu12==11.3.0.4
nvidia-cusolver-cu12==11.7.1.2
nvidia-cusparse-cu12==12.5.4.2
nvidia-nccl-cu12==2.23.4
nvidia-nvjitlink-cu12==12.6.77
opt_einsum==3.4.0
pillow==11.0.0
pip==24.3.1
rdkit==2024.3.5
scipy==1.14.1
setuptools==65.5.0
tabulate==0.9.0
toolz==1.0.0
tqdm==4.67.0
triton==3.1.0
typeguard==2.13.3
typing_extensions==4.12.2
zstandard==0.23.0
```

</details>

To re-check the module mapping, run on a submission node:

```bash
module spider alphafold/3.0.0
module show alphafold/3.0.0
```

Inspect the identified image on a submission node without reserving a GPU:

```bash
ml load apptainer
af_sif='/nbi/software/containers/e8edb411-7374-4342-b9f1-408da41fc197/e8edb411-7374-4342-b9f1-408da41fc197.img'
apptainer inspect --deffile "$af_sif"
apptainer exec --cleanenv "$af_sif" /alphafold3_venv/bin/python --version
apptainer exec --cleanenv "$af_sif" /alphafold3_venv/bin/python -m pip --disable-pip-version-check list --format=freeze
```

The Python path is from the supplied recipe; if the embedded recipe differs, use its environment path. These commands inspect metadata/package versions, without `--nv`, inference or model weights. The actual image is the authority for installed versions. See [Apptainer inspect](https://apptainer.org/docs/user/1.4/cli/apptainer_inspect.html).

Shared cluster facts and installation policy: [HPC_COMPATIBILITY.md](../HPC_COMPATIBILITY.md).
