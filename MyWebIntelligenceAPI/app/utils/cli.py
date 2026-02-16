"""
Utility helpers migrated from _legacy.core for CLI interoperability.
"""
from argparse import Namespace
from typing import Any, Callable, Sequence


def confirm(message: str, *, input_func: Callable[[str], str] = input) -> bool:
    """
    Confirm an action by requesting user input.

    Mirrors the legacy behaviour: only an uppercase 'Y' confirms.
    An injectable input_func is provided to ease testing.
    """
    return input_func(message) == "Y"


def check_args(args: Namespace, mandatory: Sequence[str] | str) -> bool:
    """
    Validate that all required arguments are present in parsed input arguments.
    """
    args_dict = vars(args)
    if isinstance(mandatory, str):
        mandatory = [mandatory]
    for arg in mandatory:
        if arg not in args_dict or args_dict[arg] is None:
            raise ValueError(f'Argument "{arg}" is required')
    return True


def split_arg(arg: str) -> list[str]:
    """
    Split an argument string using comma separator and return a filtered list.
    """
    if arg is None:
        return []
    return [part.strip() for part in arg.split(",") if part.strip()]


def get_arg_option(name: str, args: Namespace, set_type: Callable[[Any], Any], default: Any) -> Any:
    """
    Retrieve and type-cast an optional argument value with a default fallback.
    """
    args_dict = vars(args)
    if name in args_dict and args_dict[name] is not None:
        return set_type(args_dict[name])
    return default
