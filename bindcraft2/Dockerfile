# syntax=docker/dockerfile:1
# CUDA libraries come from the locked pip wheels, as in the upstream container.
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
        ca-certificates python3 python3-venv libgomp1 libstdc++6 && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

COPY requirements.lock /opt/container-info/requirements.lock
RUN python -m pip install --only-binary=:all: --require-hashes \
        -r /opt/container-info/requirements.lock

# Upstream v1.0.3 package, fixed to the reviewed source commit and archive checksum.
ADD --checksum=sha256:b5a996f082e5a81fc951053772cf22392481477bbd1113758f57e3eacbb09118 \
    https://codeload.github.com/PacesaLab/BindCraft2/tar.gz/c0ee638d11bc010817c2c97ee58ed5c323e664e2 /tmp/bindcraft.tar.gz
RUN mkdir /opt/bindcraft && \
    tar -xzf /tmp/bindcraft.tar.gz --strip-components=1 -C /opt/bindcraft && \
    rm /tmp/bindcraft.tar.gz && \
    python -m pip install --no-deps --no-build-isolation -e '/opt/bindcraft[cuda12]' && \
    python -m pip check && \
    python -m pip freeze --all > /opt/container-info/pip-freeze.txt && \
    printf '%s\n' 'c0ee638d11bc010817c2c97ee58ed5c323e664e2' > /opt/container-info/upstream-revision.txt && \
    chmod -R a+rX /opt/bindcraft /opt/venv /opt/container-info

# Make pip's NVIDIA libraries discoverable to JAX and its plugins.
RUN python -c "import nvidia, pathlib; print('\n'.join(sorted(str(path) for root in nvidia.__path__ for path in pathlib.Path(root).glob('*/lib'))))" \
        > /etc/ld.so.conf.d/bindcraft-cuda.conf && ldconfig

LABEL org.opencontainers.image.title="TSL container for BindCraft2" \
      org.opencontainers.image.description="Unofficial CUDA 12 packaging of unmodified BindCraft2; AlphaFold weights downloaded separately" \
      org.opencontainers.image.version="1.0.3" \
      io.bindcraft2.upstream-revision="c0ee638d11bc010817c2c97ee58ed5c323e664e2" \
      io.bindcraft2.accelerator="cuda12"

COPY --chmod=755 smoke-test.py /usr/local/bin/bindcraft2-smoke-test
WORKDIR /tmp
RUN bindcraft2-smoke-test

ENTRYPOINT []
CMD ["bindcraft2-smoke-test"]
