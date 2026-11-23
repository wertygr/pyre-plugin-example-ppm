# _ppm_

Minimal package manager for [PYRE](https://github.com/wertygr/pyre) plugins.

A package is just a zip archive fetched from a URL. `_ppm_` downloads it, unpacks it
into `plugins/`, registers the plugin in the active settings file and, if the archive
ships one, runs its install script.

- no registry: the package location is the URL you pass
- no dependency resolution, no signatures (see [warning](#warning))

## Requirements

Python 3.12+ and two libraries:

```bash
pip install rich requests
```

## Install

`_ppm_` is itself a plugin, so it must be registered before it can install anything:

1. copy the `ppm/` directory into `plugins/`;
2. add the entry to `.pyre_settings.json`:

   ```json
   {
       "plugin": {
           "_ppm_": {
               "file": "ppm/__init__.py",
               "cache": true,
               "api": true
           }
       }
   }
   ```

3. reload settings:

   ```pycon
   >>> _._ settings_reload
   ```

After that it can install other packages, and update itself, from a release:

```pycon
>>> _ppm_ install https://github.com/wertygr/pyre-plugin-example-ppm/releases/latest/download/ppm.zip
```

The link always points at the latest release, so it never goes stale.

## Commands

| command | description |
|:--|:--|
| `_ppm_ install <url>` | download a package and install it |
| `_ppm_ uninstall <name>` | remove the tracked files, directories and settings entry |
| `_ppm_ update <name>` | re-download the package from its `source_url` and reinstall it |
| `_ppm_ ls` | list installed packages and their sources |
| `_ppm_ clean` | delete the temporary `_plugin.zip` and `_plugin/` |
| `_ppm_ version` | print the ppm version |

`<url>` accepts `http://`, `https://` and `file:///absolute/path/to/package.zip`
(handy for testing a package built locally). `_ppm_ init` is accepted but does
nothing: it is reserved.

```pycon
>>> _ppm_ install https://example.com/hello.zip
>>> _ppm_ ls
>>> _ppm_ update _hello_
>>> _ppm_ uninstall _hello_
>>> _ppm_ clean
>>> _ppm_ version
```

## Package format

```text
hello.zip
├── config.json      # required
├── script.pyre      # optional
├── hello.py         # copied into plugins/
└── hello/           # directories are copied as a whole
```

`config.json`:

```json
{
    "name": "_hello_",
    "config": {
        "file": "hello.py",
        "cache": true,
        "api": true
    }
}
```

| field | description |
|:--|:--|
| `name` | required, non-empty; the plugin command and its key in settings (`_hello_`) |
| `config` | required object, copied as-is into the `plugin` section under `name` |
| `config.file` | required, non-empty; path inside `plugins/` (`hello.py`, or `hello/__init__.py` for a package) |

Everything else at the archive root is copied into `plugins/`. If the target already
exists, `_ppm_` asks before replacing it; only entries that were actually copied are
recorded in the manifest, so `uninstall` never deletes a file that `_ppm_` did not put
there. A directory is copied and tracked as a whole, so uninstalling removes it
entirely.

`script.pyre` runs after the files are copied and before the settings reload prompt.
Each non-empty line is passed to `api["pars_command"]`, so any PYRE command can be
used:

```text
_pyt-exec_ print("hello installed")
```

## State and prompts

| path | description |
|:--|:--|
| `.ppm_package.json` | manifest of installed packages: `source_url`, copied `files`, `dirs` and `config` |
| `_plugin.zip` | the downloaded archive (temporary) |
| `_plugin/` | the unpacked archive (temporary) |

The manifest entry looks like this:

```json
{
    "_hello_": {
        "name": "_hello_",
        "source_url": "https://example.com/hello.zip",
        "files": ["hello.py"],
        "dirs": [],
        "config": {"file": "hello.py", "cache": true, "api": true}
    }
}
```

`install` writes the package's `config` into the `plugin` section of the settings file
that is currently loaded (`data.settings_file`, usually `.pyre_settings.json`), then
offers to reload settings. `uninstall` removes that entry and offers the same. Without
a reload the running session keeps its old plugin table until restart.

Confirmation prompts accept `y`, `yes`, `1`, `true` or an empty line (the default is
yes); anything else declines. Declining a conflict keeps the existing file and leaves
it untracked.

`update` downloads the archive first, then removes the old tracked files and installs
from the downloaded copy, so a broken URL leaves the installed version untouched. The
manifest entry and the settings `config` are replaced with the ones from the new
archive.

Temporary files are removed at the end of `install`/`update` even if installation
fails; `_ppm_ clean` removes leftovers after an interrupted run.

## Development

```text
pyre-plugin-example-ppm/
├── ppm/            # the plugin package (a symlink into the PYRE tree in a dev checkout)
│   ├── __init__.py
│   ├── main.py
│   ├── const.py
│   ├── utils.py
│   ├── plugin.json # metadata: name, title, description, tags, blacklist, config
│   └── req.txt
├── LICENSE.md
└── README.md
```

`VERSION` lives in `ppm/const.py`. A release archive is built from the metadata with
the developer plugin `_builder_`, which writes `config.json`
(`{"name": ..., "config": ...}`) at the archive root and skips the `blacklist` patterns
(`__pycache__`, `*.pyc`, `.git`):

```pycon
>>> builder plugins/ppm/plugin.json plugins/ppm -o ppm.zip
```

Keep the asset name `ppm.zip`: the
[example index](https://github.com/wertygr/pyre-plugins-example) links
`.../releases/latest/download/ppm.zip`.

## Warning

There is no registry, no checksums, no signatures and no sandbox. A package is a zip
archive taken from an arbitrary URL, and `script.pyre` can execute arbitrary PYRE
commands, which means arbitrary Python. Archives are checked for path traversal before
extraction, but that check is not a security boundary.

## Read also

- [plugin contract](https://github.com/wertygr/pyre/blob/main/docs/plugin/plugin.md)
- [command context](https://github.com/wertygr/pyre/blob/main/docs/plugin/plugin_command_context.md)
- [plugin template](https://github.com/wertygr/pyre/blob/main/docs/plugin/plugin_template.md)
- [example plugins](https://github.com/wertygr/pyre-plugins-example)

## License

MIT - see [LICENSE.md](LICENSE.md).
