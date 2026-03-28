from typing import Any


def bind_toggle_keys(bind_target: Any, info: dict[str, Any], command=None) -> None:
    """Bind one or more toggle keys from a definition dict to a callable."""
    if "toggle_key" not in info:
        return

    callback = command if command else info.get("command")
    if callback is None:
        return

    toggle_key = info["toggle_key"]
    if isinstance(toggle_key, str):
        bind_target.bind(toggle_key, callback)
    elif isinstance(toggle_key, (tuple, list)):
        for bind_key in toggle_key:
            bind_target.bind(bind_key, callback)
