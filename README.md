# 🧬 Bio-Containers Toolbox

This is a monolithic repository ("monorepo") for managing HPC container builds. 
Each tool has its own folder and its own GitHub Actions workflow.

## Structure
- **.github/workflows/**: Contains the CI/CD automation logic.
- **tool-name/**: Contains the Dockerfile for a specific tool.

## How to add a new tool
1. Create a new folder: `mkdir new-tool`
2. Add a `Dockerfile` inside that folder.
3. Copy an existing workflow file in `.github/workflows/` (e.g., `build-new-tool.yml`).
4. Update the `paths` and `context` in the workflow to point to your new folder.

## Usage on HPC
To pull a specific container:
`singularity pull tool-name.sif docker://ghcr.io/YOUR_USERNAME/tool-name:latest`
