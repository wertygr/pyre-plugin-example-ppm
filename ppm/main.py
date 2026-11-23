import json
import shutil
import zipfile

import os
from pathlib import Path

import requests
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)


from plugins.plugin_tools.plugin_types import CommandContext, PluginApi, PluginData
from plugins.plugin_tools.lib.base import base_destructor
from rich import box
from rich.table import Table
from rich.text import Text
from .utils import (
    console,
    get_file_name,
    json_load,
    require_args,
    validate,
)
from .const import (
    PACKAGE_FILE,
    PLUGIN_DIR,
    PLUGIN_NAME,
    VERSION,
    ZIP_DIR,
    ZIP_FILE,
)


# ______________________________________________________________________________________

def destructor(plugin_space: dict) -> None:
    plugin_space.pop(PLUGIN_NAME, None)
    base_destructor(__package__)


def version(**__) -> None:
    console.print(VERSION, style="bold")


def clean(**__) -> None:
    if os.path.isfile(ZIP_FILE):
        os.remove(ZIP_FILE)
        console.print(Text.assemble(("deleted ", "green"), (ZIP_FILE, "yellow")))

    if os.path.isdir(ZIP_DIR):
        shutil.rmtree(ZIP_DIR)
        console.print(Text.assemble(("deleted ", "green"), (ZIP_DIR, "yellow")))


def download(url: str) -> None:
    output_path = Path(ZIP_FILE)
    if url.startswith("file://"):
        console.print(Text.assemble(("copy local package: ", "green"), (url, "yellow")))
        shutil.copy2(url.removeprefix("file://"), output_path)
        return
    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()

        total = int(response.headers.get("Content-Length", 0)) or None

        progress = Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )

        with progress:
            task_id = progress.add_task(
                "download",
                filename=output_path.name,
                total=total,
            )

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

    console.print(Text.assemble(("downloaded ", "green"), (url, "yellow")))

def json_save(path: os.DirEntry | str, data: dict | list) -> None:
    name = get_file_name(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=4))
    console.print(Text.assemble(("saved", "green"), (": ", ""), (name, "yellow")))


def unzip() -> None:
    root = os.path.abspath(ZIP_DIR)
    with zipfile.ZipFile(ZIP_FILE, "r") as zf:
        for member in zf.infolist():
            target = os.path.abspath(os.path.join(root, member.filename))
            try:
                inside = os.path.commonpath((root, target)) == root
            except ValueError:
                inside = False
            if not inside:
                raise ValueError(f"unsafe path in archive: {member.filename}")
        zf.extractall(ZIP_DIR)


def setup_script(data, text: str) -> None:
    for line in text.splitlines():
        if not line.strip():
            continue
        data.command = line
        data.api["pars_command"](data)


def manifest_load() -> dict:
    if not os.path.isfile(PACKAGE_FILE):
        return {}
    return json_load(PACKAGE_FILE)


def save_package(package_json: dict) -> None:
    manifest = manifest_load()
    manifest[package_json["name"]] = package_json
    json_save(PACKAGE_FILE, manifest)


def settings_path(data) -> str:
    return getattr(data, "settings_file")


def enable_plugin(package_json: dict, data: PluginData) -> str:
    path = data.settings_file
    settings = json_load(path)
    settings.setdefault("plugin", {})[package_json["name"]] = package_json.get("config", {})
    json_save(path, settings)
    return path


def disable_plugin(package_name: str, data) -> None:
    path = settings_path(data)
    if not os.path.isfile(path):
        return
    settings = json_load(path)
    plugin_settings = settings.get("plugin", {})
    if package_name in plugin_settings:
        del plugin_settings[package_name]
        json_save(path, settings)


# ______________________________________________________________________________________

def copy_file(path: os.DirEntry, package_json: dict) -> None:
    target = os.path.join(PLUGIN_DIR, path.name)
    if os.path.exists(target):
        if not validate(f"conflict: file: \"{path.name}\" already exists. replace? [Y/n]"):
            return
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
    shutil.copy2(path, PLUGIN_DIR)
    package_json["files"].append(path.name)
    console.print(Text.assemble(
        ("copy files", "green"), (": ", ""),
        (f"{ZIP_DIR}/{path.name}", "yellow"), (" -> ", ""),
        (f"{PLUGIN_DIR}/{path.name}", "yellow"),
    ))


def copy_dir(src: os.DirEntry, package_json: dict) -> None:
    target = os.path.join(PLUGIN_DIR, src.name)
    if os.path.exists(target):
        if not validate(f"conflict: dir: \"{src.name}\" already exists. replace? [Y/n]"):
            return
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
    shutil.copytree(src.path, target)
    package_json["dirs"].append(src.name)
    console.print(Text.assemble(
        ("copy dir", "green"), (": ", ""),
        (f"{ZIP_DIR}/{src.name}", "yellow"), (" -> ", ""),
        (f"{PLUGIN_DIR}/{src.name}", "yellow"),
    ))


def extract_script(path: os.DirEntry) -> str:
    with open(path, "r", encoding="utf-8") as f:
        script = f.read()
    console.print("extract script", style="green")
    return script


# ______________________________________________________________________________________

def validate_package_json(package_json: dict) -> None:
    name = package_json.get("name")
    config = package_json.get("config")
    if not name or not isinstance(name, str):
        raise ValueError("Invalid structure: package must contain a non-empty 'name'")
    if not isinstance(config, dict) or not config.get("file"):
        raise ValueError("Invalid structure: package must contain a non-empty 'config.file'")


def extract_config(path: os.DirEntry, package_json: dict) -> None:
    json_data = json_load(path)
    if not isinstance(json_data, dict):
        raise ValueError("Invalid structure: config.json must contain an object")
    package_json["name"] = json_data.get("name")
    config = json_data.get("config", {})
    package_json["config"] = config if isinstance(config, dict) else {}
    validate_package_json(package_json)
    console.print("extract config", style="green")


def install_manager(package_json: dict) -> str:
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    entries = list(os.scandir(ZIP_DIR))

    config_entry = next((i for i in entries if i.is_file() and i.name == "config.json"), None)
    if config_entry is None:
        raise ValueError("Invalid structure: config.json not found in archive")
    extract_config(config_entry, package_json)

    for i in entries:
        if i.is_file() and i.name in ("config.json", "script.pyre"):
            continue
        if i.is_file():
            copy_file(i, package_json)
        elif i.is_dir():
            copy_dir(i, package_json)

    script_entry = next((i for i in entries if i.is_file() and i.name == "script.pyre"), None)
    return extract_script(script_entry) if script_entry else ""


# ______________________________________________________________________________________

def _uninstall(package_name: str, manifest: dict) -> dict:
    package = manifest[package_name]
    for name in package.get("files", []):
        path = os.path.join(PLUGIN_DIR, name)
        if os.path.isfile(path):
            os.remove(path)
            console.print(Text.assemble(("deleted ", "green"), (name, "yellow")))
        else:
            console.print(Text.assemble(("missing ", "yellow"), (name, "yellow")))
    for name in package.get("dirs", []):
        path = os.path.join(PLUGIN_DIR, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
            console.print(Text.assemble(("deleted ", "green"), (name, "yellow")))
        else:
            console.print(Text.assemble(("missing ", "yellow"), (name, "yellow")))
    del manifest[package_name]
    return manifest


@require_args(3)
def uninstall(api: dict, command_context: dict) -> None:
    name = command_context["argv"][2]
    manifest = manifest_load()
    if name not in manifest:
        api["post"](f"[ppm::uninstall]: not package: \"{name}\"", api["data"])
        return
    if not validate(f"delete \"{name}\" [Y/n]: "):
        return
    _uninstall(name, manifest)
    disable_plugin(name, api["data"])
    json_save(PACKAGE_FILE, manifest)
    if validate("reload settings [Y/n]: "):
        api["settings_load"](api["data"], settings_path(api["data"]))


def _install(url: str, api: dict, already_downloaded: bool = False) -> None:
    data = api["data"]
    package_json = {
        "name": None,
        "source_url": url,
        "files": [],
        "dirs": [],
        "config": {},
    }
    if not already_downloaded:
        download(url)

    try:
        unzip()
        script = install_manager(package_json)
    finally:
        clean()

    path = enable_plugin(package_json, data)
    save_package(package_json)

    if script:
        console.print("run_script", style="cyan")
        setup_script(data, script)

    if validate("reload settings [Y/n]: "):
        api["settings_load"](data, path)


@require_args(3)
def install(api, command_context: dict) -> None:
    _install(command_context["argv"][2], api)


def list_packages(**__) -> None:
    manifest = manifest_load()
    if not manifest:
        console.print("no packages installed", style="dim")
        return
    table = Table(title="installed packages", box=box.SIMPLE, highlight=False)
    table.add_column("name", style="yellow", no_wrap=True)
    table.add_column("source")
    for name, package in manifest.items():
        source_url = package.get("source_url", "") if isinstance(package, dict) else ""
        table.add_row(name, source_url)
    console.print(table)


@require_args(3)
def update(api: dict, command_context: dict) -> None:
    name = command_context["argv"][2]
    manifest = manifest_load()
    if name not in manifest:
        api["post"](f"[ppm::update]: not package: \"{name}\"", api["data"])
        return
    if not validate(f"update: \"{name}\" [Y/n]: "):
        return

    url = manifest[name]["source_url"]
    download(url)  # download first so a broken URL does not remove the installed version
    _uninstall(name, manifest)
    json_save(PACKAGE_FILE, manifest)
    _install(url, api, already_downloaded=True)


# ______________________________________________________________________________________

def main(api: PluginApi, command_context: CommandContext, plugin_space: dict) -> None:
    post = api["post"]
    data = api["data"]
    if command_context["argc"] < 2:
        post("[ppm::main]: not enough arguments", data)
        return
    command_map = {
        "install": install,
        "uninstall": uninstall,
        "ls": list_packages,
        "clean": clean,
        "update": update,
        "version": version,
        "init": lambda **__: None,
    }
    command = command_context["argv"][1]
    if command not in command_map:
        post(f"[ppm::main]: unknown command {command}", data)
        return

    command_map[command](api=api, command_context=command_context)
    console.print("done", style="bold green")
