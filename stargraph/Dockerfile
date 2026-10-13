# Official Miniforge base, pinned to the verified 26.7.2-0 image contents.
FROM quay.io/condaforge/miniforge3:26.7.2-0@sha256:16eff7459a31bed2d395b1df0dca220c067a3a9527981ec87dbbde2eafe474e5

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Runtime utilities and compatibility library for older bioinformatics binaries.
RUN apt-get update && \
    apt-get install --yes --no-install-recommends procps libcrypt1 && \
    rm -rf /var/lib/apt/lists/*

# conda-forge before Bioconda; SAMtoBAM is needed only for this tool.
# Keep certificate verification enabled. Pin the published package and build.
RUN mamba create --yes --name tool --override-channels --strict-channel-priority \
        --channel conda-forge --channel bioconda --channel samtobam \
        "samtobam::stargraph=1.0.0=0" && \
    mkdir -p /opt/container-info && \
    conda list --name tool --explicit > /opt/container-info/conda-explicit.txt && \
    mamba clean --all --yes && \
    chmod -R a+rX /opt/conda/envs/tool /opt/container-info

ENV PATH="/opt/conda/envs/tool/bin:/opt/conda/bin:$PATH" \
    CONDA_PREFIX="/opt/conda/envs/tool" \
    CONDA_DEFAULT_ENV="tool"
WORKDIR /data

ENTRYPOINT []
RUN ["stargraph.sh", "--help"]
CMD ["stargraph.sh", "--help"]
