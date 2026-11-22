import json
import os
from functools import wraps
from typing import Callable

from rich.console import Console
from rich.text import Text

console = Console(highlight=False, soft_wrap=True)

def require_args(min_args: int) -> Callable[[Callable], Callable]:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(api: dict, command_context: dict):
            if command_context["argc"] < min_args:
                api["post"](f"[ppm::{func.__name__}]: not enough arguments", api["data"])
                return None
            return func(api, command_context)
        return wrapper
    return decorator


def get_file_name(path: os.DirEntry|str) -> str:
    if isinstance(path, str):
        return path
    return path.name


def validate(message: str = "") -> bool:
    return input(message).lower() in ["", "y", "yes", "1", "true"]


def json_load(path: os.DirEntry|str) -> dict|list:
    name = get_file_name(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    console.print(Text.assemble(("open", "green"), (": ", ""), (name, "yellow")))
    return data
