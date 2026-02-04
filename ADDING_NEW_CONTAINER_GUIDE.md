# 🛠️ How to Add a New Tool

Follow this guide to add a new bioinformatics tool to this repository. This workflow ensures that:

1. You don't overwrite existing containers
2. You only rebuild what is necessary
3. You get a ready-to-use container on the HPC in minutes

---

## 1. Create the Tool Folder

Create a new directory at the root of the repo with the name of your tool (e.g., `samtools`, `bcftools`).
```bash
mkdir my-new-tool
```

---

## 2. Create the Dockerfile

Create a `Dockerfile` inside that folder (`my-new-tool/Dockerfile`).

**Pro Tip:** Use the "Hardened" template below to avoid network/SSL issues on the HPC.
```dockerfile
FROM quay.io/almalinux/almalinux:9

# 1. System dependencies (SSL fix)
RUN dnf -y update && \
    dnf -y install wget which bzip2 ca-certificates libxcrypt-compat openssl && \
    dnf clean all

# 2. Install Miniforge
RUN wget --no-check-certificate https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh && \
    bash Miniforge3-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniforge3-Linux-x86_64.sh

ENV PATH="/opt/conda/bin:$PATH"

# 3. Configure Network & Channels (Crucial for robustness)
RUN conda config --set ssl_verify false && \
    conda config --add channels https://repo.prefix.dev/conda-forge && \
    conda config --add channels https://repo.prefix.dev/bioconda && \
    conda config --add channels samtobam && \
    conda config --set channel_priority strict

# 4. Install Your Tool
# REPLACE 'toolname' with the actual package name
RUN mamba create -y -n myenv toolname && \
    mamba clean -a

# 5. Final Setup
ENV PATH="/opt/conda/envs/myenv/bin:$PATH"
WORKDIR /data

# 6. Verify & Set Command
# Run a quick ls to find the binary name if you are unsure: RUN ls -F /opt/conda/envs/myenv/bin/
CMD ["toolname", "--help"]
```

---

## 3. Create the GitHub Workflow

This is the most critical step. We need to tell GitHub how to build this specific folder.

1. Go to `.github/workflows/`
2. Copy an existing file (e.g., `build-stargraph.yml`) and name it `build-my-new-tool.yml`
3. Edit the file and change these 4 lines:

| Field | Change To | Why? |
|-------|-----------|------|
| `name:` | `Build My New Tool` | So you can identify it in the Actions tab |
| `paths:` | `- 'my-new-tool/**'` | **CRITICAL:** Only triggers build when this folder changes |
| `context:` | `./my-new-tool` | Tells Docker where the Dockerfile is |
| `tags:` | `.../my-new-tool:latest` | **CRITICAL:** Prevents overwriting other containers |

**Example YAML:**
```yaml
name: Build My New Tool             # <--- CHANGE 1

on:
  push:
    branches: [ "main", "master" ]
    paths:
      - 'my-new-tool/**'            # <--- CHANGE 2

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Log in to the Container registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: ./my-new-tool    # <--- CHANGE 3
          push: true
          tags: ghcr.io/${{ github.repository_owner }}/my-new-tool:latest  # <--- CHANGE 4
```

---

## 4. Push to GitHub

Commit your changes. GitHub will detect the new file and start building immediately.
```bash
git add .
git commit -m "Add my-new-tool"
git push
```

---

## 5. Pull on the HPC

Once the build is **Green** on GitHub Actions, log in to the HPC and pull it:
```bash
singularity pull my-new-tool.sif docker://ghcr.io/georgedeeks/my-new-tool:latest
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build ignored? | Check that the `paths:` in the YAML matches your folder name exactly |
| Overwrote another tool? | Check the `tags:` line in the YAML |
| Command not found? | Add `RUN ls -F /opt/conda/envs/myenv/bin/` to the Dockerfile to see actual executable names |
