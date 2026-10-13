#!/usr/bin/env bash
# Run on software23 from a checkout of this repository after installing SIF/weights.
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
install_dir="${1:-/tsl/software/testing/BindCraft2/1.0.3/x86_64}"
[[ "$install_dir" == /* && -r "$install_dir/bindcraft2.sif" ]] || {
    printf 'Pass the existing absolute installation directory containing bindcraft2.sif.\n' >&2
    exit 2
}
[[ -d "$install_dir/weights/alphafold" ]] || {
    printf 'Stage the shared AlphaFold parameters before installing the launcher.\n' >&2
    exit 2
}
install -d -m 755 "$install_dir/bin" "$install_dir/examples"
install -m 755 "$source_dir/bin/bindcraft" "$install_dir/bin/bindcraft"
install -m 644 "$source_dir/run-wrapper.slurm" "$source_dir/example-settings.json" "$install_dir/examples/"
install -m 644 "$source_dir/README.md" "$install_dir/README.md"
printf 'Installed launcher: %s/bin/bindcraft\n' "$install_dir"
printf 'Next register the software with the TSL wrapper generator (see README).\n'
