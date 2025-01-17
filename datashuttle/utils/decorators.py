from functools import wraps

from datashuttle.utils.utils import log_and_raise_error


def requires_ssh_configs(func):
    """
    Decorator to check file is loaded. Used on Mainwindow class
    methods only as first arg is assumed to be self (containing cfgs)
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if (
            not args[0].cfg["central_host_id"]
            or not args[0].cfg["central_host_username"]
        ):
            log_and_raise_error(
                "Cannot setup SSH connection, 'central_host_id' "
                "or 'central_host_username' is not set in "
                "the configuration file."
            )
        else:
            return func(*args, **kwargs)

    return wrapper


def check_configs_set(func):
    """
    Check that configs have been loaded (i.e.
    project.cfg is not None) before the
    func is run.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        if args[0].cfg is None:
            log_and_raise_error(
                "Must set configs with make_config_file() "
                "before using this function."
            )
        else:
            return func(*args, **kwargs)

    return wrapper
