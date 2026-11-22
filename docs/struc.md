# _ppm_

A tiny npm-style package manager for PYRE plugins.

## commands

```text
_ppm_ install <url>     download and install a package
_ppm_ uninstall <name>  remove an installed package
_ppm_ update <name>     reinstall a package from its source_url
_ppm_ ls                list installed packages
_ppm_ clean             remove temporary _plugin/ and _plugin.zip
_ppm_ version           print the ppm version
```

## package structure

```text
zip\
 |_ config.json      # required: {"name": "...", "config": {...}}
 |_ script.pyre      # optional: PYRE commands executed after install
 |_ Any file/dir     # copied into ./plugins/
```

`config.json`:

```json
{
    "name": "_example_",
    "config": {
        "file": "example.py",
        "cache": true,
        "api": true
    }
}
```

`config.config` is written as-is into the `plugin` section of the active settings file
(`data.settings_file`, usually `.pyre_settings.json`).

`script.pyre` is executed line by line through `data.api["pars_command"]`, so it can use
any PYRE command.

## state

* `.ppm_package.json` - installed packages, their `source_url`, `files`, `dirs` and `config`.
* `_plugin/`, `_plugin.zip` - temporary files, removed by `clean` (and after install).

Files and directories are tracked in the manifest only after they are actually copied,
so a declined conflict prompt does not make `uninstall` delete a pre-existing file.
`uninstall` also removes the plugin entry from the active settings file.

## warning

There is no registry, no signatures and no dependency resolution: a package is just a
zip archive fetched from a URL, and `script.pyre` can execute arbitrary PYRE commands.
Archives are checked for path traversal before extraction, but the code is still a
joke, not a security boundary.
