# TSL shared software wrappers

Recorded from the user's creator source, site template and successful HPC output on 2026-10-13. The creator is maintained separately from this container repository; do not keep a second implementation here.

## Three parts of a container installation

1. The **site loader**, `/tsl/software/testing/bin/NAME-VERSION`, is sourced by users. Preserve its `core/header`, `source hpccore-5` and `core/footer` logic. Its application-specific section loads Apptainer, adds the installation's `x86_64/bin` to PATH and may print useful locations.
2. The **executable launcher**, `NAME/VERSION/x86_64/bin/COMMAND`, calls Apptainer and supplies the image, weights, scratch paths and tool-specific GPU settings. Preserve the caller's arguments, working directory and exit status.
3. The **SIF and external data**, under `NAME/VERSION/x86_64/`, provide the actual application. Libraries inside the SIF do not need host Python or library-path setup. Large external weights can stay beside the SIF; outputs and caches belong to each user.

The creator also writes `hpcdata.db` in the version directory for the site catalogue. Give new entries a useful description and categories, preferably with `--desc` and `--categories` to avoid empty interactive answers. An existing empty description is a catalogue tidying task, not an application failure; do not use `--force` merely to fix metadata, because it also replaces the loader.

The [BindCraft2 instructions](../bindcraft2/README.md#install-the-tsl-command-launcher) contain the concrete tested layout and app-specific section. A successful creator verification confirms sourcing of the initial template; test the application command after editing that section too.

## Creator fixes to retain

The reviewed `create-tsl-testing-wrapper` source includes these changes, and the user subsequently reported successful creation and clean-shell verification:

- Test shared-bin write access by creating a temporary file. The site's Isilon ACLs can disagree with visible POSIX permissions and `test -w`; a real write attempt is the useful check.
- Use isolated system Python (`/usr/bin/python3` or `/usr/libexec/platform-python`, with `-I` and library overrides cleared) for SQLite. Do not load an EasyBuild SQLite module to create catalogue metadata.
- Create the database on local `/tmp`, then copy it to a staging file in the version directory and rename it into place. This avoids SQLite locking on shared storage and publishing a partially copied database.
- Bound Python checks/metadata creation with 10-second timeouts and clean-login-shell verification with a 30-second timeout. These do not bound every shared-filesystem operation.
- Print progress, log failures and preserve created files if verification fails. Inspect those files before retrying; the creator refuses to overwrite a loader without `--force`.

The original log stopped before metadata completion. The exact cause of that earlier stall was not established; the later implementation succeeded. No further creator code change is required by the successful BindCraft2 result.

## Keep the source, deployed copy and README consistent

- Maintainer source: `~/my-software-wrapper/bin/create-tsl-testing-wrapper` on the HPC.
- Shared command: `/tsl/software/testing/bin/create-tsl-testing-wrapper`.
- Log: `/tsl/software/testing/bin/create-tsl-testing-wrapper.log`.

Running `./create-tsl-testing-wrapper` from the source directory does not establish that the shared command was updated. Once any concurrent editing is finished, compare the copies:

```bash
cmp "$HOME/my-software-wrapper/bin/create-tsl-testing-wrapper" \
    /tsl/software/testing/bin/create-tsl-testing-wrapper
```

No output and exit status zero means they match. If the source is the intended tested version, deploy it with the existing procedure:

```bash
install -m 775 "$HOME/my-software-wrapper/bin/create-tsl-testing-wrapper" \
    /tsl/software/testing/bin/create-tsl-testing-wrapper
```

Update that project's README to describe system-Python SQLite, local database staging, progress messages and bounded verification. Its older claim that it loads an EasyBuild SQLite module or skips metadata when SQLite is absent is stale: the reviewed version fails clearly if system Python SQLite is unavailable. Verification failure keeps created files and returns status 2. Keep the documented source/deployment paths above.

The container repo does not have direct access to the HPC creator checkout. Its source/deployment equality and README update must be confirmed there; the working BindCraft2 installation does not need recreating.
