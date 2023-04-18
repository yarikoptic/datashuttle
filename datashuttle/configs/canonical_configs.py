"""
This module contains all information for the required
format of the configs class. This is clearly defined
as configs can be provided from file or input dynamically
and so careful checks must be done.

If adding a new config, first add the key to
get_canonical_config_dict( and type to
get_canonical_config_required_types()
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from datashuttle.configs.configs import Configs

from pathlib import Path
from typing import Union, get_args

from datashuttle.utils import utils


def get_canonical_config_dict() -> dict:
    """
    The only permitted keys in the
    DataShuttle config.
    """
    config_dict = {
        "local_path": None,
        "remote_path": None,
        "connection_method": None,
        "remote_host_id": None,
        "remote_host_username": None,
    }

    data_type_configs = get_data_types(as_dict=True)
    config_dict.update(data_type_configs)

    return config_dict


def get_data_types(as_dict: bool = False):
    """
    New data_types must be added here
    """
    keys = ["use_ephys", "use_behav", "use_funcimg", "use_histology"]

    if as_dict:
        return dict(zip(keys, [None] * len(keys)))
    else:
        return keys


def get_flags() -> List[str]:
    """
    Return all configs that are bool flags. This is used in
    testing and type checking config inputs.
    """
    return get_data_types()


def get_canonical_config_required_types() -> dict:
    """
    The only permitted types for DataShuttle
    config values.
    """
    required_types = {
        "local_path": Union[str, Path],
        "remote_path": Union[str, Path],
        "connection_method": str,
        "remote_host_id": Union[str, None],
        "remote_host_username": Union[str, None],
        "use_ephys": bool,
        "use_behav": bool,
        "use_funcimg": bool,
        "use_histology": bool,
    }

    assert (
        required_types.keys() == get_canonical_config_dict().keys()
    ), "update get_canonical_config_required_types with required types."

    return required_types


# -------------------------------------------------------------------
# Check Configs
# -------------------------------------------------------------------


def check_dict_values_and_inform_user(config_dict: Configs) -> None:
    """
    Central function for performing checks on a
    DataShuttle Configs UserDict class. This should
    be run after any change to the configs (e.g.
    make_config_file, update_config, supply_config_file).

    This will raise assert if condition is not met.
    """
    canonical_dict = get_canonical_config_dict()

    for key in canonical_dict.keys():
        if key not in config_dict.keys():
            utils.raise_error(
                f"Loading Failed. The key {key} was not "
                f"found in the supplied config. "
                f"Config file was not updated."
            )

    for key in config_dict.keys():
        if key not in canonical_dict.keys():
            utils.raise_error(
                f"The supplied config contains an invalid key: {key}. "
                f"Config file was not updated."
            )

    check_config_types(config_dict)

    if list(config_dict.keys()) != list(canonical_dict.keys()):
        utils.raise_error(
            f"New config keys are in the wrong order. The"
            f" order should be: {canonical_dict.keys()}"
        )

    if config_dict["connection_method"] not in ["ssh", "local_filesystem"]:
        utils.raise_error("connection method must be ssh or local_filesystem")

    for path_ in ["local_path", "remote_path"]:
        if config_dict[path_].as_posix()[0] == "~":
            utils.raise_error(
                f"{path_} must contain the full directory path "
                "with no ~ syntax"
            )

    if not any([config_dict[key] for key in get_data_types()]):
        utils.raise_error(
            f"At least one data_type must be True in "
            f"configs, from: {' '.join(get_data_types())}"
        )

    # Check SSH settings
    if config_dict["connection_method"] == "ssh" and (
        not config_dict["remote_host_id"]
        or not config_dict["remote_host_username"]
    ):
        utils.raise_error(
            "remote_host_id and remote_host_username are "
            "required if connection_method is ssh."
        )


def check_config_types(config_dict: Configs) -> None:
    """
    Check the type of passed configs matched canonical types.
    This is a little awkward as testing types against
    Union is not neat. To do this you can use
    isinstance(type, get_args(Union[types])).
    But get_args() will be empty if there is only
    one type in union. So we need to test the
    two cases explicitly.
    """
    required_types = get_canonical_config_required_types()
    fail = False

    for key in config_dict.keys():

        expected_type = required_types[key]

        if len(get_args(required_types[key])) == 0:
            if not isinstance(config_dict[key], expected_type):
                fail = True
        else:
            if not isinstance(config_dict[key], get_args(expected_type)):
                fail = True

        if fail:
            utils.raise_error(
                f"The type of the value at {key} is incorrect, "
                f"it must be {expected_type}. "
                f"Config file was not updated."
            )
