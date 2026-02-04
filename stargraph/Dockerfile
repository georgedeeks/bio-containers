FROM quay.io/almalinux/almalinux:9

# 1. System dependencies
RUN dnf -y update && \
    dnf -y install wget which bzip2 ca-certificates libxcrypt-compat openssl && \
    dnf clean all

# 2. Install Miniforge
RUN wget --no-check-certificate https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh && \
    bash Miniforge3-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniforge3-Linux-x86_64.sh

# 3. Path Setup
ENV PATH="/opt/conda/bin:$PATH"

# 4. Config: SSL Verify False + Strict Channels
RUN conda config --set ssl_verify false && \
    conda config --add channels https://repo.prefix.dev/conda-forge && \
    conda config --add channels https://repo.prefix.dev/bioconda && \
    conda config --add channels samtobam && \
    conda config --set channel_priority strict

# 5. Create Environment
RUN mamba create -y -n stargraph stargraph && \
    mamba clean -a

# 6. Finalize
ENV PATH="/opt/conda/envs/stargraph/bin:$PATH"
WORKDIR /data

# Verify installation
RUN stargraph.sh --help

# Default command
CMD ["stargraph.sh", "--help"]
