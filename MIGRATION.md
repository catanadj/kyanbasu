# Migrating to Kyanbasu

Kyanbasu is the new product identity for TaskCanvas. Version `0.2.0` changes the
preferred commands and runtime names without requiring users to discard their
existing installation or browser workspace.

## Upgrade

Update the checkout and reinstall the editable package:

```bash
git pull
python3 -m pip install -e .
kyanbasu --version
```

For a wheel installation, rebuild and reinstall the wheel from the updated
checkout:

```bash
python3 -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
python3 -m pip install --upgrade dist/taskwarrior_canvas-0.2.0-py3-none-any.whl
```

The install distribution remains named `taskwarrior-canvas`. Keeping that name
allows package managers to upgrade an existing installation instead of creating
a second, conflicting distribution.

## Preferred entry points

Use one of these Kyanbasu entry points for new scripts and documentation:

```bash
kyanbasu
python3 -m kyanbasu
python3 Kyanbasu.py
```

The following compatibility entry points remain supported in `0.2.x`:

```bash
taskcanvas
python3 -m taskcanvas
python3 TaskCanvas.py
```

Both command families accept the same arguments. The generated file is still
named `TaskCanvas.html`, so existing launch scripts and browser bookmarks do not
need to change yet.

## Browser data

No manual state conversion is required. On first access, Kyanbasu copies values
from recognized `taskcanvas:*` local-storage keys into their corresponding
`kyanbasu:*` keys. Existing layouts, notes, workbenches, snapshots, and UI
preferences remain available.

New exports use these identifiers and filenames:

- `kyanbasu.notes` in `kyanbasu-notes.json`
- `kyanbasu.workbenches` in `kyanbasu-workbenches.json`
- `kyanbasu-reviewed-commands.sh` for reviewed command downloads

Imports continue to accept the legacy `taskcanvas.notes` and
`taskcanvas.workbenches` formats.

## Browser integrations

Use the `window.Kyanbasu*` APIs for new integrations. Existing
`window.TaskCanvas*` globals are synchronized compatibility aliases and remain
available during the migration period.

Before clearing browser storage or moving to another browser profile, export
the notes or full workbench set from the current workspace. Generated HTML can
contain task data and should not be published or attached to bug reports.

## Repository identity

The source repository remains at `catanadj/taskwarrior-canvas` for this release.
GitHub redirects can preserve old clone and issue links if the repository is
renamed later, but that hosting change is independent from the application and
package migration in `0.2.0`.
