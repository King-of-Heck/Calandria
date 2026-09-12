"""The launcher's shortcut, written as Shell Link bytes (no COM, no PowerShell)."""
import os
import struct

import pytest

from calandria.server import shortcut as sc


def _parse(data: bytes) -> dict:
    """A small reader of the parts this writer produces, in the order the format lays them out."""
    assert data[:4] == b"\x4c\0\0\0" and data[4:20] == sc._CLSID_SHELL_LINK
    flags, attrs = struct.unpack_from("<II", data, 20)
    show, = struct.unpack_from("<I", data, 60)
    pos = 0x4C
    out = {"flags": flags, "attrs": attrs, "show": show, "items": []}
    if flags & sc._HAS_LINK_TARGET_ID_LIST:
        size, = struct.unpack_from("<H", data, pos)
        end = pos + 2 + size
        p = pos + 2
        while True:
            item_size, = struct.unpack_from("<H", data, p)
            if item_size == 0:
                break
            out["items"].append(data[p + 2:p + item_size])
            p += item_size
        assert p + 2 == end
        pos = end
    if flags & sc._HAS_LINK_INFO:
        size, hsize, li_flags, vol_off, base_off, cnrl_off, suffix_off, base_uni_off, suffix_uni_off = \
            struct.unpack_from("<IIIIIIIII", data, pos)
        assert hsize == 0x24 and li_flags == 1 and cnrl_off == 0
        vol = data[pos + vol_off:]
        vol_size, drive_type, serial, label_off = struct.unpack_from("<IIII", vol, 0)
        assert vol_size == 0x11 and drive_type == 3 and label_off == 0x10 and vol[16] == 0
        ansi = data[pos + base_off:data.index(b"\0", pos + base_off)]
        uni_end = data.index(b"\0\0", pos + base_uni_off)
        while (uni_end - (pos + base_uni_off)) % 2:
            uni_end = data.index(b"\0\0", uni_end + 1)
        out["base_ansi"] = ansi
        out["base"] = data[pos + base_uni_off:uni_end].decode("utf-16-le")
        assert data[pos + suffix_off] == 0 and data[pos + suffix_uni_off:pos + suffix_uni_off + 2] == b"\0\0"
        pos += size
    for flag, key in ((sc._HAS_NAME, "name"), (sc._HAS_RELATIVE_PATH, "relative"),
                      (sc._HAS_WORKING_DIR, "working_dir"), (0x20, "arguments"),
                      (sc._HAS_ICON_LOCATION, "icon")):
        if flags & flag:
            n, = struct.unpack_from("<H", data, pos)
            out[key] = data[pos + 2:pos + 2 + 2 * n].decode("utf-16-le")
            pos += 2 + 2 * n
    assert data[pos:] == b"\0\0\0\0"                                          # the terminal block, nothing after
    return out


def test_shortcut_bytes_carry_the_target_in_the_id_list_and_the_link_info():
    data = sc.shortcut_bytes(r"C:\Tools\Calandria\Calandria.cmd", r"C:\Tools\Calandria",
                             r"C:\Tools\Calandria\Calandria.ico", "Calandria", r".\Calandria.cmd")
    p = _parse(data)
    assert p["show"] == 1 and p["attrs"] == 0x20                             # SW_SHOWNORMAL, an archive file
    assert p["flags"] & sc._IS_UNICODE
    assert p["base"] == r"C:\Tools\Calandria\Calandria.cmd" and p["base_ansi"] == b"C:\\Tools\\Calandria\\Calandria.cmd"
    assert p["name"] == "Calandria" and p["relative"] == r".\Calandria.cmd"
    assert p["working_dir"] == r"C:\Tools\Calandria" and p["icon"] == r"C:\Tools\Calandria\Calandria.ico"
    assert "arguments" not in p
    root, drive, tools, cal, cmd = p["items"]
    assert root == sc._ROOT_MY_COMPUTER
    assert drive[0] == 0x2F and drive[1:5] == b"C:\\\0" and len(drive) == 23     # the 0x19-byte volume item
    for item, name, kind in ((tools, b"Tools", 0x31), (cal, b"Calandria", 0x31), (cmd, b"Calandria.cmd", 0x32)):
        assert item[0] == kind and item[12:].rstrip(b"\0") == name
        assert len(item) % 2 == 0                                            # word-aligned
    assert struct.unpack_from("<H", tools, 10)[0] == 0x10 and struct.unpack_from("<H", cmd, 10)[0] == 0x20


def test_shortcut_bytes_without_a_relative_path():
    p = _parse(sc.shortcut_bytes(r"D:\x\a.cmd", r"D:\x", r"D:\x\a.ico", "A"))
    assert "relative" not in p and p["base"] == r"D:\x\a.cmd" and [i[0] for i in p["items"]] == [0x1F, 0x2F, 0x31, 0x32]


def test_a_name_outside_the_code_page_does_not_raise():
    data = sc.shortcut_bytes("C:\\\u4e2d\\a.cmd", "C:\\\u4e2d", "C:\\\u4e2d\\a.ico", "A")
    assert _parse(data)["base"] == "C:\\\u4e2d\\a.cmd"                        # the Unicode path is intact


def test_write_shortcut_needs_the_icon_and_writes_once(tmp_path):
    cmd = tmp_path / "Calandria.cmd"
    cmd.write_text("@echo off\r\n")
    assert sc.write_shortcut(str(cmd)) == "no icon"
    assert not (tmp_path / "Calandria.lnk").exists()
    (tmp_path / "Calandria.ico").write_bytes(b"\0\0\1\0")
    assert sc.write_shortcut(str(cmd)) == "written"
    lnk = tmp_path / "Calandria.lnk"
    p = _parse(lnk.read_bytes())
    assert p["base"] == str(cmd) and p["icon"] == str(tmp_path / "Calandria.ico")
    assert p["working_dir"] == str(tmp_path) and p["relative"] == r".\Calandria.cmd"
    before = lnk.stat().st_mtime_ns
    assert sc.write_shortcut(str(cmd)) == "unchanged"                        # a synced folder is not churned
    assert lnk.stat().st_mtime_ns == before
    lnk.write_bytes(b"stale")
    assert sc.write_shortcut(str(cmd)) == "written"


@pytest.mark.skipif(os.name != "nt", reason="the Windows shell reads the file back")
def test_the_windows_shell_resolves_the_written_shortcut(tmp_path):
    """The shell's own reader (WScript.Shell through PowerShell, which the desktop allows) sees the
    target, the working folder and the icon. Skipped where PowerShell or COM is not available."""
    import subprocess
    cmd = tmp_path / "Calandria.cmd"
    cmd.write_text("@echo off\r\n")
    (tmp_path / "Calandria.ico").write_bytes(b"\0\0\1\0")
    assert sc.write_shortcut(str(cmd)) == "written"
    script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CAL_LNK);"
              "$s.TargetPath; $s.WorkingDirectory; $s.IconLocation; $s.Description")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "CAL_LNK": str(tmp_path / "Calandria.lnk")})
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("no PowerShell")
    if r.returncode != 0 or "language mode" in r.stderr.lower():
        pytest.skip("PowerShell cannot create COM objects here")
    assert r.stdout.splitlines() == [str(cmd), str(tmp_path), str(tmp_path / "Calandria.ico") + ",0", "Calandria"]
