# syntax=docker/dockerfile:1
# CUDA 12.6 libraries come from the hashed PyTorch/NVIDIA wheels.
# A runtime image avoids shipping the large upstream CUDA development toolchain.
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
        ca-certificates python3 python3-venv python3-dev gcc \
        libgomp1 libstdc++6 libxrender1 libxext6 hmmer kalign && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LAYERNORM_TYPE=torch \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

COPY requirements.in requirements.lock /opt/container-info/
# modelcif 1.4 is a source-only package. Use a pinned build backend, then
# validate the complete dependency graph with pip check after installing it.
RUN python -m pip install setuptools==80.9.0 wheel==0.45.1 && \
    python -m pip install --require-hashes --no-build-isolation \
        -r /opt/container-info/requirements.lock

# Protenix v1.0.9 supports the requested protenix_base_default_v1.0.0 model.
# Both the source revision and its downloaded archive are pinned.
ADD --checksum=sha256:fc596dd0a1e95942531408a741e510af06a179e223505badae98489b90d9d4eb \
    https://codeload.github.com/bytedance/Protenix/tar.gz/510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d /tmp/protenix.tar.gz
RUN mkdir /opt/protenix && \
    tar -xzf /tmp/protenix.tar.gz --strip-components=1 -C /opt/protenix && \
    rm /tmp/protenix.tar.gz && \
    cp /opt/protenix/requirements.txt /opt/container-info/upstream-requirements.txt && \
    python -c "from pathlib import Path; p=Path('/opt/container-info/requirements.in'); Path('/opt/protenix/requirements.txt').write_text('\n'.join(line for line in p.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))+'\n')" && \
    cd /opt/protenix && \
    python -m pip install --no-deps --no-build-isolation -e . && \
    python -m pip check && \
    python -m pip freeze --all > /opt/container-info/pip-freeze.txt && \
    printf '%s\n' '510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d' > /opt/container-info/upstream-revision.txt && \
    chmod -R a+rX /opt/protenix /opt/container-info

LABEL org.opencontainers.image.title="TSL Protenix v1 inference" \
      org.opencontainers.image.description="Protenix v1.0.9 with curated inference dependencies and native Torch kernels; model weights downloaded separately" \
      org.opencontainers.image.version="1.0.9" \
      org.opencontainers.image.licenses="Apache-2.0" \
      io.protenix.upstream-revision="510faf9f5cc8fbbbb8d9055934d3fa7e6877c76d" \
      io.protenix.model="protenix_base_default_v1.0.0" \
      io.protenix.accelerator="cuda12.6" \
      io.protenix.packaging="inference-only dependency metadata; application source unchanged"

COPY --chmod=755 bin/ /usr/local/bin/
COPY --chmod=755 summarize-confidence.py /usr/local/bin/protenix-summarize
COPY --chmod=755 smoke-test.py /usr/local/bin/protenix-smoke-test
COPY --chmod=644 example-smoke.json /opt/protenix-example-smoke.json
WORKDIR /tmp
RUN protenix-smoke-test

ENTRYPOINT []
CMD ["protenix-smoke-test"]
