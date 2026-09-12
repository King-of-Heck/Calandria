"""Write a Windows shortcut (.lnk) without COM or PowerShell.

A .cmd cannot carry an icon; a shortcut can. The launcher used to refresh `Calandria.lnk`
through `WScript.Shell` in an inline PowerShell command, which a locked-down machine refuses
(Constrained Language Mode allows no COM objects). The Shell Link binary format (MS-SHLLINK)
is small enough to write by hand: a header, a LinkInfo block naming the target by its local
path, and the string data (description, relative path, working folder, icon). No item-id list
is written; the shell resolves the local base path, and falls back to the relative path when
the folder has moved (the launcher rewrites the file on every start anyway, so a moved folder
is followed at its next launch).
"""
from __future__ import annotations

import os
import struct

_CLSID_SHELL_LINK = bytes.fromhex("0114020000000000C000000000000046")
_ROOT_MY_COMPUTER = bytes.fromhex("1F50E04FD020EA3A6910A2D808002B30309D")   # 0x1F, sort index, CLSID
_HAS_LINK_TARGET_ID_LIST = 0x01
_HAS_LINK_INFO = 0x02
_HAS_NAME = 0x04
_HAS_RELATIVE_PATH = 0x08
_HAS_WORKING_DIR = 0x10
_HAS_ICON_LOCATION = 0x40
_IS_UNICODE = 0x80
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_ARCHIVE = 0x20
_SW_SHOWNORMAL = 1
_DRIVE_FIXED = 3
LINK_NAME = "Calandria.lnk"
ICON_NAME = "Calandria.ico"


def _string_data(s: str) -> bytes:
    """CountCharacters + UTF-16LE characters, no terminator (the IsUnicode form)."""
    data = s.encode("utf-16-le")
    return struct.pack("<H", len(data) // 2) + data


def _link_info(target: str) -> bytes:
    """LinkInfo with a VolumeID and the local base path, in both the ANSI and the Unicode form."""
    ansi = target.encode("mbcs", errors="replace") if os.name == "nt" else target.encode("ascii", errors="replace")
    volume = struct.pack("<IIII", 0x11, _DRIVE_FIXED, 0, 0x10) + b"\0"      # empty label at offset 0x10
    header_size = 0x24
    base_off = header_size + len(volume)
    suffix_off = base_off + len(ansi) + 1
    base_uni_off = suffix_off + 1
    suffix_uni_off = base_uni_off + len(target.encode("utf-16-le")) + 2
    body = volume + ansi + b"\0" + b"\0" + target.encode("utf-16-le") + b"\0\0" + b"\0\0"
    size = header_size + len(body)
    header = struct.pack("<IIIIIIIII", size, header_size, 1, header_size, base_off, 0, suffix_off,
                         base_uni_off, suffix_uni_off)
    return header + body


def _item(data: bytes) -> bytes:
    return struct.pack("<H", len(data) + 2) + data


def _id_list(target: str) -> bytes:
    """The LinkTargetIDList: My Computer, the drive, then one file-entry item per path component
    (the pre-Vista form: type, size, time and attributes left zero, the name in the system code
    page, no long-name extension block; the shell resolves it and fills the rest in itself)."""
    drive, rest = os.path.splitdrive(target)
    parts = [p for p in rest.split(os.sep) if p]
    items = [_item(_ROOT_MY_COMPUTER)]
    drive_data = (drive + "\\").encode("ascii") + b"\0"
    items.append(_item(b"\x2f" + drive_data.ljust(22, b"\0")))              # the 0x19-byte volume item
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        name = (part.encode("mbcs", errors="replace") if os.name == "nt" else part.encode("ascii", errors="replace")) + b"\0"
        if len(name) % 2:
            name += b"\0"                                                    # items are word-aligned
        items.append(_item(struct.pack("<BBIIH", 0x32 if last else 0x31, 0, 0, 0,
                                       _FILE_ATTRIBUTE_ARCHIVE if last else _FILE_ATTRIBUTE_DIRECTORY) + name))
    body = b"".join(items) + b"\0\0"
    return struct.pack("<H", len(body)) + body


def shortcut_bytes(target: str, working_dir: str, icon: str, description: str,
                   relative: str | None = None) -> bytes:
    """The bytes of a shortcut to `target` (an absolute path) with `icon` (index 0)."""
    flags = (_HAS_LINK_TARGET_ID_LIST | _HAS_LINK_INFO | _HAS_NAME | _HAS_WORKING_DIR
             | _HAS_ICON_LOCATION | _IS_UNICODE)
    if relative:
        flags |= _HAS_RELATIVE_PATH
    header = struct.pack("<I", 0x4C) + _CLSID_SHELL_LINK + struct.pack(
        "<IIQQQIiIHHII", flags, _FILE_ATTRIBUTE_ARCHIVE, 0, 0, 0, 0, 0, _SW_SHOWNORMAL, 0, 0, 0, 0)
    out = header + _id_list(target) + _link_info(target) + _string_data(description)
    if relative:
        out += _string_data(relative)
    out += _string_data(working_dir) + _string_data(icon)
    return out + b"\0\0\0\0"                                                 # the terminal block


def write_shortcut(cmd_path: str) -> str:
    """Refresh `Calandria.lnk` beside the launcher `cmd_path`, with `Calandria.ico` from the same
    folder. Returns "written", "unchanged" (the bytes already match, so a synced folder is not
    touched) or "no icon". Errors are the caller's to report: nothing here may stop the app."""
    cmd_path = os.path.abspath(cmd_path)
    folder = os.path.dirname(cmd_path)
    icon = os.path.join(folder, ICON_NAME)
    if not os.path.isfile(icon):
        return "no icon"
    lnk = os.path.join(folder, LINK_NAME)
    data = shortcut_bytes(cmd_path, folder, icon, "Calandria", ".\\" + os.path.basename(cmd_path))
    try:
        with open(lnk, "rb") as f:
            if f.read() == data:
                return "unchanged"
    except OSError:
        pass
    with open(lnk, "wb") as f:
        f.write(data)
    return "written"
