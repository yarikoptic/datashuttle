from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datashuttle.configs.config_class import Configs

import fnmatch
import getpass
import stat
from pathlib import Path
from typing import Any, List, Optional, Tuple

import paramiko

from . import utils

# --------------------------------------------------------------------------------------------------------------------
# SSH
# --------------------------------------------------------------------------------------------------------------------


def setup_ssh_key(
    cfg: Configs,
    log: bool = True,
) -> None:
    """
    Set up an SSH private / public key pair with
    central server. First, a private key is generated
    and saved in the .datashuttle config path.
    Next a connection requiring input
    password made, and the public part of the key
    added to ~/.ssh/authorized_keys.

    Parameters
    -----------

    ssh_key_path : path to the ssh private key

    hostkeys_path : path to the ssh host key, once the user
        has confirmed the key ID this is saved so verification
        is not required each time.

    cfg : datashuttle config UserDict

    log : log if True, logger must already be initialised.
    """
    generate_and_write_ssh_key(cfg.ssh_key_path)

    password = getpass.getpass(
        "Please enter password to your central host to add the public key. "
        "You will not have to enter your password again."
    )

    key = paramiko.RSAKey.from_private_key_file(cfg.ssh_key_path.as_posix())

    add_public_key_to_central_authorized_keys(cfg, password, key)

    success_message = (
        f"SSH key pair setup successfully. "
        f"Private key at: {cfg.ssh_key_path.as_posix()}"
    )

    utils.print_message_to_user(success_message)

    if log:
        utils.log(f"\n{success_message}")


def connect_client(
    client: paramiko.SSHClient,
    cfg: Configs,
    password: Optional[str] = None,
) -> None:
    """
    Connect client to central server using paramiko.
    Accept either password or path to private key, but not both.
    Paramiko does not support pathlib.
    """
    try:
        client.get_host_keys().load(cfg.hostkeys_path.as_posix())
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            cfg["central_host_id"],
            username=cfg["central_host_username"],
            password=password,
            key_filename=cfg.ssh_key_path.as_posix()
            if isinstance(cfg.ssh_key_path, Path)
            else None,
            look_for_keys=True,
        )
        utils.print_message_to_user(
            f"Connection to { cfg['central_host_id']} made successfully."
        )

    except Exception:
        utils.log_and_raise_error(
            f"Could not connect to server. Ensure that \n"
            f"1) You have run setup_ssh_connection_to_central_server() \n"
            f"2) You are on VPN network if required. \n"
            f"3) The central_host_id: {cfg['central_host_id']} is"
            f" correct.\n"
            f"4) The central username:"
            f" {cfg['central_host_username']}, and password are correct."
        )


def add_public_key_to_central_authorized_keys(
    cfg: Configs, password: str, key: paramiko.RSAKey
) -> None:
    """
    Append the public part of key to central server ~/.ssh/authorized_keys.
    """
    client: paramiko.SSHClient
    with paramiko.SSHClient() as client:

        connect_client(client, cfg, password=password)

        client.exec_command("mkdir -p ~/.ssh/")
        client.exec_command(
            # double >> for concatenate
            f'echo "{key.get_name()} {key.get_base64()}" '
            f">> ~/.ssh/authorized_keys"
        )
        client.exec_command("chmod 644 ~/.ssh/authorized_keys")
        client.exec_command("chmod 700 ~/.ssh/")


def verify_ssh_central_host(
    central_host_id: str, hostkeys_path: Path, log: bool = True
) -> bool:
    """
    Similar to connecting with other SSH manager e.g. putty,
    get the server key and present when connecting
    for manual validation.
    """
    transport: paramiko.Transport
    with paramiko.Transport(central_host_id) as transport:
        transport.connect()
        key = transport.get_remote_server_key()

    message = (
        f"The host key is not cached for this server: "
        f"{central_host_id}.\nYou have no guarantee "
        f"that the server is the computer you think it is.\n"
        f"The server's {key.get_name()} key fingerprint is: "
        f"{key.get_base64()}\nIf you trust this host, to connect"
        f" and cache the host key, press y: "
    )
    input_ = utils.get_user_input(message)

    if input_ == "y":
        client = paramiko.SSHClient()
        client.get_host_keys().add(central_host_id, key.get_name(), key)
        client.get_host_keys().save(hostkeys_path.as_posix())
        success = True
        utils.print_message_to_user("Host accepted.")
    else:
        utils.print_message_to_user("Host not accepted. No connection made.")
        success = False

    if log:
        if success:
            utils.log(f"{message}")
            utils.log(f"Hostkeys saved at:{hostkeys_path.as_posix()}")
        else:
            utils.log("Host not accepted. No connection made.")

    return success


def generate_and_write_ssh_key(ssh_key_path: Path) -> None:
    key = paramiko.RSAKey.generate(4096)
    key.write_private_key_file(ssh_key_path.as_posix())


def search_ssh_central_for_folders(
    search_path: Path,
    search_prefix: str,
    cfg: Configs,
    verbose: bool = True,
) -> Tuple[List[Any], List[Any]]:
    """
    Search for the search prefix in the search path over SSH.
    Returns the list of matching folders, files are filtered out.

    Parameters
    -----------

    search_path : path to search for folders in

    search_prefix : search prefix for folder names e.g. "sub-*"

    cfg : see connect_client()

    verbose : If `True`, if a search folder cannot be found, a message
      will be printed with the un-found path.

    """
    client: paramiko.SSHClient
    with paramiko.SSHClient() as client:
        connect_client(client, cfg)

        sftp = client.open_sftp()

        all_folder_names, all_filenames = get_list_of_folder_names_over_sftp(
            sftp,
            search_path,
            search_prefix,
            verbose,
        )

    return all_folder_names, all_filenames


def get_list_of_folder_names_over_sftp(
    sftp, search_path: Path, search_prefix: str, verbose: bool = True
) -> Tuple[List[Any], List[Any]]:
    """
    Use paramiko's sftp to search a path
    over ssh for folders. Return the folder names.

    Parameters
    ----------

    stfp : connected paramiko stfp object
        (see search_ssh_central_for_folders())

    search_path : path to search for folders in

    search_prefix : prefix (can include wildcards)
        to search folder names.

    verbose : If `True`, if a search folder cannot be found, a message
          will be printed with the un-found path.
    """
    all_folder_names = []
    all_filenames = []
    try:
        for file_or_folder in sftp.listdir_attr(search_path.as_posix()):

            if fnmatch.fnmatch(file_or_folder.filename, search_prefix):
                if stat.S_ISDIR(file_or_folder.st_mode):
                    all_folder_names.append(file_or_folder.filename)
                else:
                    all_filenames.append(file_or_folder.filename)

    except FileNotFoundError:
        if verbose:
            utils.log_and_message(f"No file found at {search_path.as_posix()}")

    return all_folder_names, all_filenames
