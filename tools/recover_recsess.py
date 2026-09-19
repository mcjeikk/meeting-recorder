"""Recupera segmentos recsess_* borrados leyendo la MFT de NTFS (solo Windows).

Uso (como Administrador):
    python recover_recsess.py --scan
    python recover_recsess.py --copy
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import os
import struct
import sys
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path


GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.SetFilePointerEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_longlong,
    ctypes.POINTER(ctypes.c_longlong),
    wintypes.DWORD,
]
kernel32.SetFilePointerEx.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
kernel32.GetFileSizeEx.restype = wintypes.BOOL

NAME_HINTS = (
    "video_seg",
    "video_final",
    "system_seg",
    "mic_seg_",
    "recsess_",
)
NAME_HINTS_U16 = [h.encode("utf-16le") for h in NAME_HINTS]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def _enable_privileges() -> None:
    names = ("SeBackupPrivilege", "SeRestorePrivilege", "SeManageVolumePrivilege")
    tok = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(tok)
    ):
        return
    try:
        for name in names:
            luid = LUID()
            if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
                continue
            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            advapi32.AdjustTokenPrivileges(tok, False, ctypes.byref(tp), 0, None, None)
    finally:
        kernel32.CloseHandle(tok)


def _open_volume(letter: str = "C") -> int:
    _enable_privileges()
    path = f"\\\\.\\{letter}:"
    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == INVALID_HANDLE_VALUE or handle is None:
        err = ctypes.get_last_error()
        raise OSError(err, f"No se pudo abrir {path}. Ejecuta como Administrador. winerr={err}")
    return handle


def _seek(handle: int, pos: int) -> None:
    newp = ctypes.c_longlong(0)
    if not kernel32.SetFilePointerEx(handle, pos, ctypes.byref(newp), 0):
        raise OSError(ctypes.get_last_error(), f"seek {pos}")


def _read(handle: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    done = wintypes.DWORD(0)
    if not kernel32.ReadFile(handle, buf, size, ctypes.byref(done), None):
        raise OSError(ctypes.get_last_error(), f"read {size}")
    return buf.raw[: done.value]


def _read_at(handle: int, pos: int, size: int) -> bytes:
    """Lee el volumen NTFS. ReadFile exige tamaño y offset alineados al sector."""
    if size <= 0:
        return b""
    sector = 512
    aligned_pos = (pos // sector) * sector
    skip = pos - aligned_pos
    aligned_size = ((skip + size + sector - 1) // sector) * sector
    _seek(handle, aligned_pos)
    data = _read(handle, aligned_size)
    got = data[skip : skip + size]
    if len(got) != size:
        raise OSError(0, f"short read @ {pos}: {len(got)}/{size}")
    return got


@dataclass
class Boot:
    bytes_per_sector: int
    sectors_per_cluster: int
    mft_lcn: int
    record_size: int
    cluster_size: int


def parse_boot(raw: bytes) -> Boot:
    if raw[3:11] != b"NTFS    ":
        raise RuntimeError("El volumen no parece NTFS")
    bps = struct.unpack_from("<H", raw, 0x0B)[0]
    spc = raw[0x0D]
    mft_lcn = struct.unpack_from("<q", raw, 0x30)[0]
    cpr = struct.unpack_from("b", raw, 0x40)[0]
    rec = (2 ** abs(cpr)) if cpr < 0 else cpr * bps * spc
    cluster = bps * spc
    return Boot(bps, spc, mft_lcn, rec, cluster)


def apply_fixup(record: bytearray, rec_size: int) -> None:
    if record[0:4] not in (b"FILE", b"BAAD"):
        return
    usa_off = struct.unpack_from("<H", record, 0x04)[0]
    usa_count = struct.unpack_from("<H", record, 0x06)[0]
    if usa_off == 0 or usa_count < 2:
        return
    usa = record[usa_off : usa_off + usa_count * 2]
    if len(usa) < 2:
        return
    for i in range(1, usa_count):
        pos = i * 512 - 2
        if pos + 2 <= rec_size:
            record[pos : pos + 2] = usa[i * 2 : i * 2 + 2]


def decode_runs(mapping: bytes) -> list[tuple[int, int]]:
    """Devuelve lista (lcn, cluster_count). lcn=None => sparse."""
    runs: list[tuple[int | None, int]] = []
    i = 0
    prev = 0
    while i < len(mapping) and mapping[i] != 0:
        header = mapping[i]
        i += 1
        len_len = header & 0x0F
        off_len = header >> 4
        if i + len_len + off_len > len(mapping):
            break
        ncl = int.from_bytes(mapping[i : i + len_len], "little")
        i += len_len
        if off_len == 0:
            lcn = None
        else:
            rel = int.from_bytes(mapping[i : i + off_len], "little", signed=True)
            i += off_len
            prev += rel
            lcn = prev
        runs.append((lcn, ncl))
    return runs


def _filetime_to_dt(ft: int) -> dt.datetime | None:
    if ft <= 0:
        return None
    try:
        utc = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=ft / 10)
        return utc.astimezone().replace(tzinfo=None)
    except OverflowError:
        return None


@dataclass
class DataPart:
    start_vcn: int
    real_size: int
    resident: bytes | None = None
    runs: list[tuple[int | None, int]] = field(default_factory=list)


@dataclass
class FoundFile:
    mft_ref: int
    names: list[str]
    size: int
    in_use: bool
    is_dir: bool
    created: dt.datetime | None
    modified: dt.datetime | None
    parent_refs: set[int]
    data_runs: list
    record_bytes: bytes
    extra_refs: set[int] = field(default_factory=set)
    data_parts: list[DataPart] = field(default_factory=list)
    attr_list_runs: list[tuple[int | None, int]] = field(default_factory=list)
    attr_list_size: int = 0
    base_ref: int = 0


def _parse_attr_list(blob: bytes) -> set[int]:
    refs: set[int] = set()
    i = 0
    while i + 26 <= len(blob):
        elen = struct.unpack_from("<H", blob, i + 4)[0]
        if elen < 26 or i + elen > len(blob):
            break
        raw_ref = blob[i + 16 : i + 22] + b"\x00\x00"
        refs.add(struct.unpack("<Q", raw_ref)[0])
        i += elen
    return refs


def _iter_attrs(buf: bytearray, rec_size: int):
    off = struct.unpack_from("<H", buf, 0x14)[0]
    while off + 8 <= rec_size:
        atype = struct.unpack_from("<I", buf, off)[0]
        if atype == 0xFFFFFFFF:
            break
        alen = struct.unpack_from("<I", buf, off + 4)[0]
        if alen < 8 or off + alen > rec_size:
            break
        yield off, atype, alen
        off += alen


def describe_record(rec: bytes, rec_size: int, idx: int) -> str:
    if rec[0:4] != b"FILE":
        return f"MFT#{idx} sig={rec[0:4]!r} hex={rec[:16].hex()}"
    buf = bytearray(rec)
    apply_fixup(buf, rec_size)
    flags = struct.unpack_from("<H", buf, 0x16)[0]
    base = struct.unpack_from("<Q", buf, 0x20)[0] & 0x0000FFFFFFFFFFFF
    used = struct.unpack_from("<I", buf, 0x18)[0]
    types = []
    for off, atype, alen in _iter_attrs(buf, rec_size):
        nonres = buf[off + 8]
        name_len = buf[off + 9]
        extra = ""
        if atype == 0x80 and nonres:
            alloc = struct.unpack_from("<Q", buf, off + 40)[0]
            real_size = struct.unpack_from("<Q", buf, off + 48)[0]
            init = struct.unpack_from("<Q", buf, off + 56)[0]
            start_vcn = struct.unpack_from("<Q", buf, off + 16)[0]
            last_vcn = struct.unpack_from("<Q", buf, off + 24)[0]
            mp_off = struct.unpack_from("<H", buf, off + 32)[0]
            mp = bytes(buf[off + mp_off : off + alen]).hex()
            extra = f" sz={real_size} alloc={alloc} init={init} vcn={start_vcn}-{last_vcn} mp={mp}"
        elif atype == 0x20:
            if nonres:
                alloc = struct.unpack_from("<Q", buf, off + 40)[0]
                real_size = struct.unpack_from("<Q", buf, off + 48)[0]
                mp_off = struct.unpack_from("<H", buf, off + 32)[0]
                extra = f" ATTRLIST nr sz={real_size} alloc={alloc} mp={bytes(buf[off+mp_off:off+alen]).hex()}"
            else:
                voff = struct.unpack_from("<H", buf, off + 20)[0]
                vlen = struct.unpack_from("<I", buf, off + 16)[0]
                blob = bytes(buf[off + voff : off + voff + vlen])
                extra = f" ATTRLIST r refs={sorted(_parse_attr_list(blob))} hex={blob.hex()}"
        types.append(f"0x{atype:X}/{'nr' if nonres else 'r'}{extra} nlen={name_len} alen={alen}")
    parsed = parse_record(rec, rec_size, idx)
    names = parsed.names if parsed else []
    size = parsed.size if parsed else -1
    return (
        f"MFT#{idx} flags={flags:#x} base={base} used={used} names={names} "
        f"parsed_size={size} attrs=[{'; '.join(types)}]"
    )


def _extract_data_part(buf: bytearray, off: int, alen: int) -> DataPart | None:
    nonres = buf[off + 8]
    name_len = buf[off + 9]
    name_off = struct.unpack_from("<H", buf, off + 10)[0]
    aname = ""
    if name_len and name_off:
        aname = buf[off + name_off : off + name_off + name_len * 2].decode("utf-16le", "replace")
    if aname != "":
        return None
    if nonres == 0:
        voff = struct.unpack_from("<H", buf, off + 20)[0]
        vlen = struct.unpack_from("<I", buf, off + 16)[0]
        return DataPart(0, vlen, resident=bytes(buf[off + voff : off + voff + vlen]))
    start_vcn = struct.unpack_from("<Q", buf, off + 16)[0]
    real_size = struct.unpack_from("<Q", buf, off + 48)[0]
    mp_off = struct.unpack_from("<H", buf, off + 32)[0]
    runs = decode_runs(bytes(buf[off + mp_off : off + alen]))
    return DataPart(start_vcn, real_size, runs=runs)


def parse_record(rec: bytes, rec_size: int, mft_ref: int) -> FoundFile | None:
    if rec[0:4] != b"FILE":
        return None
    buf = bytearray(rec)
    apply_fixup(buf, rec_size)
    flags = struct.unpack_from("<H", buf, 0x16)[0]
    base_ref = struct.unpack_from("<Q", buf, 0x20)[0] & 0x0000FFFFFFFFFFFF
    names: list[str] = []
    parent_refs: set[int] = set()
    created = modified = None
    extra_refs: set[int] = set()
    parts: list[DataPart] = []
    attr_list_runs: list[tuple[int | None, int]] = []
    attr_list_size = 0
    for off, atype, alen in _iter_attrs(buf, rec_size):
        nonres = buf[off + 8]
        if atype == 0x10 and nonres == 0:
            voff = struct.unpack_from("<H", buf, off + 20)[0]
            c = struct.unpack_from("<Q", buf, off + voff)[0]
            m = struct.unpack_from("<Q", buf, off + voff + 8)[0]
            created = _filetime_to_dt(c)
            modified = _filetime_to_dt(m)
        elif atype == 0x20:
            if nonres == 0:
                voff = struct.unpack_from("<H", buf, off + 20)[0]
                vlen = struct.unpack_from("<I", buf, off + 16)[0]
                extra_refs |= _parse_attr_list(bytes(buf[off + voff : off + voff + vlen]))
            else:
                mp_off = struct.unpack_from("<H", buf, off + 32)[0]
                attr_list_size = struct.unpack_from("<Q", buf, off + 48)[0]
                attr_list_runs = decode_runs(bytes(buf[off + mp_off : off + alen]))
        elif atype == 0x30 and nonres == 0:
            voff = struct.unpack_from("<H", buf, off + 20)[0]
            parent = struct.unpack_from("<Q", buf, off + voff)[0] & 0x0000FFFFFFFFFFFF
            nlen = buf[off + voff + 64]
            rawname = buf[off + voff + 66 : off + voff + 66 + nlen * 2]
            fname = rawname.decode("utf-16le", "replace")
            if fname:
                names.append(fname)
                parent_refs.add(parent)
        elif atype == 0x80:
            part = _extract_data_part(buf, off, alen)
            if part is not None:
                parts.append(part)
    data_runs: list = []
    data_size = 0
    resident_parts = [p for p in parts if p.resident is not None and p.start_vcn >= 0]
    run_parts = [p for p in parts if p.resident is None and p.start_vcn >= 0]
    if resident_parts:
        data_size = resident_parts[0].real_size
        data_runs = [("__resident_bytes__", resident_parts[0].resident)]
    elif run_parts:
        run_parts.sort(key=lambda p: p.start_vcn)
        for p in run_parts:
            data_runs.extend(p.runs)
            data_size = max(data_size, p.real_size)
    if not names and not data_runs and not extra_refs and not attr_list_runs:
        return None
    return FoundFile(
        mft_ref=mft_ref,
        names=names,
        size=data_size,
        in_use=bool(flags & 0x01),
        is_dir=bool(flags & 0x02),
        created=created,
        modified=modified,
        parent_refs=parent_refs,
        data_runs=data_runs,
        record_bytes=bytes(buf),
        extra_refs=extra_refs,
        data_parts=parts,
        attr_list_runs=attr_list_runs,
        attr_list_size=attr_list_size,
        base_ref=base_ref,
    )


def load_mft_runs(handle: int, boot: Boot) -> list[tuple[int | None, int]]:
    rec = _read_at(handle, boot.mft_lcn * boot.cluster_size, boot.record_size)
    parsed = parse_record(rec, boot.record_size, 0)
    if not parsed or not parsed.data_runs:
        raise RuntimeError("No se pudieron leer los data runs de $MFT")
    if parsed.data_runs and parsed.data_runs[0] and parsed.data_runs[0][0] in (
        "__resident__",
        "__resident_bytes__",
    ):
        raise RuntimeError("$MFT residente inesperado")
    return parsed.data_runs  # type: ignore[return-value]


def mft_record_at(
    handle: int, boot: Boot, mft_runs: list[tuple[int | None, int]], idx: int
) -> bytes:
    byte_off = idx * boot.record_size
    walked = 0
    for lcn, ncl in mft_runs:
        span = ncl * boot.cluster_size
        if walked + span > byte_off:
            if lcn is None:
                raise RuntimeError(f"$MFT sparse en idx {idx}")
            pos = lcn * boot.cluster_size + (byte_off - walked)
            return _read_at(handle, pos, boot.record_size)
        walked += span
    raise RuntimeError(f"$MFT idx {idx} fuera de rango")


def _read_runs_blob(handle: int, boot: Boot, runs: list[tuple[int | None, int]], size: int) -> bytes:
    out = bytearray()
    remain = size
    for lcn, ncl in runs:
        if remain <= 0:
            break
        take = min(ncl * boot.cluster_size, remain)
        if lcn is None:
            out.extend(b"\x00" * take)
        else:
            out.extend(_read_at(handle, lcn * boot.cluster_size, take))
        remain -= take
    return bytes(out[:size])


def _rebuild_data(item: FoundFile) -> None:
    parts = [p for p in item.data_parts if p.start_vcn >= 0]
    resident_parts = [p for p in parts if p.resident is not None]
    run_parts = [p for p in parts if p.resident is None]
    if resident_parts:
        item.size = resident_parts[0].real_size
        item.data_runs = [("__resident_bytes__", resident_parts[0].resident)]
        return
    run_parts.sort(key=lambda p: p.start_vcn)
    runs: list = []
    size = 0
    for p in run_parts:
        runs.extend(p.runs)
        size = max(size, p.real_size)
    item.data_runs = runs
    item.size = size


def resolve_item(handle: int, boot: Boot, mft_runs: list, item: FoundFile) -> None:
    if item.attr_list_runs:
        blob = _read_runs_blob(handle, boot, item.attr_list_runs, item.attr_list_size)
        item.extra_refs |= _parse_attr_list(blob)
    for ref in sorted(item.extra_refs):
        if ref == item.mft_ref or ref <= 0:
            continue
        try:
            rec = mft_record_at(handle, boot, mft_runs, ref)
        except Exception:
            continue
        extra = parse_record(rec, boot.record_size, ref)
        if extra is None:
            continue
        if extra.base_ref != item.mft_ref:
            continue
        item.data_parts.extend(extra.data_parts)
        if extra.names and not item.names:
            item.names = extra.names
        item.parent_refs |= extra.parent_refs
    _rebuild_data(item)


def iter_mft_records(handle: int, boot: Boot, mft_runs: list[tuple[int | None, int]]):
    rec_size = boot.record_size
    idx = 0
    for lcn, ncl in mft_runs:
        if lcn is None:
            idx += (ncl * boot.cluster_size) // rec_size
            continue
        remaining = ncl * boot.cluster_size
        pos = lcn * boot.cluster_size
        chunk = 1024 * rec_size
        while remaining > 0:
            take = min(remaining, chunk)
            raw = _read_at(handle, pos, take)
            for off in range(0, take, rec_size):
                yield idx, raw[off : off + rec_size]
                idx += 1
            pos += take
            remaining -= take


def _interesting_name(names: list[str]) -> bool:
    joined = " ".join(names).lower()
    return any(h in joined for h in NAME_HINTS)


def _in_window(ts: dt.datetime | None, start: dt.datetime, end: dt.datetime) -> bool:
    if ts is None:
        return False
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return start <= ts <= end


SESSION_PARENT_MARK = (1076264).to_bytes(6, "little")


def scan(
    handle: int,
    boot: Boot,
    mft_runs: list[tuple[int | None, int]],
    start: dt.datetime,
    end: dt.datetime,
) -> list[FoundFile]:
    found: list[FoundFile] = []
    for idx, rec in iter_mft_records(handle, boot, mft_runs):
        if rec[0:4] != b"FILE":
            continue
        looks = any(h in rec for h in NAME_HINTS_U16) or SESSION_PARENT_MARK in rec
        if not looks:
            continue
        parsed = parse_record(rec, boot.record_size, idx)
        if parsed is None:
            continue
        if 1076264 in parsed.parent_refs:
            found.append(parsed)
            continue
        if not _interesting_name(parsed.names):
            continue
        if parsed.in_use and not any(n.startswith("recsess_") for n in parsed.names):
            continue
        if not parsed.in_use or any(n.startswith("recsess_") for n in parsed.names):
            found.append(parsed)
    return found


def read_file_data(handle: int, boot: Boot, item: FoundFile, limit: int | None = None) -> bytes:
    out = bytearray()
    remaining = item.size if limit is None else min(item.size, limit)
    runs = item.data_runs
    if runs and runs[0] and runs[0][0] in ("__resident__", "__resident_bytes__"):
        if runs[0][0] == "__resident_bytes__":
            data = runs[0][1] or b""
            return data[:remaining]
        _, off, vlen = runs[0]
        rec = bytearray(item.record_bytes)
        return bytes(rec[off : off + min(vlen, remaining)])
    for lcn, ncl in runs:  # type: ignore[assignment]
        if remaining <= 0:
            break
        nbytes = ncl * boot.cluster_size
        take = min(nbytes, remaining)
        if lcn is None:
            out.extend(b"\x00" * take)
        else:
            out.extend(_read_at(handle, lcn * boot.cluster_size, take))
        remaining -= take
    return bytes(out[: item.size if limit is None else min(item.size, limit)])


def copy_file(
    handle: int,
    boot: Boot,
    item: FoundFile,
    dest: Path,
    overwrite_target: Path | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if overwrite_target is not None and overwrite_target.exists():
        # Reutiliza clústeres YA asignados (p. ej. recsess viejo) para no pisar los borrados.
        target = overwrite_target
        mode = "r+b"
        existing = overwrite_target.stat().st_size
        if existing < item.size:
            raise RuntimeError(
                f"{overwrite_target} ({existing} bytes) es más pequeño que el archivo a recuperar ({item.size})"
            )
    else:
        target = dest
        mode = "wb"
    copied = 0
    with open(target, mode) as fh:
        if mode == "r+b":
            fh.seek(0)
        runs = item.data_runs
        remaining = item.size
        if runs and runs[0] and runs[0][0] in ("__resident__", "__resident_bytes__"):
            data = read_file_data(handle, boot, item)
            fh.write(data)
            copied = len(data)
        else:
            for lcn, ncl in runs:  # type: ignore[assignment]
                if remaining <= 0:
                    break
                nbytes = ncl * boot.cluster_size
                take = min(nbytes, remaining)
                if lcn is None:
                    chunk = b"\x00" * take
                else:
                    chunk = _read_at(handle, lcn * boot.cluster_size, take)
                fh.write(chunk)
                copied += take
                remaining -= take
                fh.flush()
        fh.truncate(item.size)
    if overwrite_target is not None and overwrite_target.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        os.replace(str(overwrite_target), str(dest))
    return dest


def _fmt(item: FoundFile) -> str:
    name = item.names[0] if item.names else "?"
    ts = item.modified or item.created
    ts_s = ts.isoformat(sep=" ", timespec="seconds") if ts else "?"
    state = "vivo" if item.in_use else "BORRADO"
    kind = "dir" if item.is_dir else "file"
    return (
        f"MFT#{item.mft_ref} {state} {kind} {name!r} {item.size} bytes "
        f"mtime={ts_s} names={item.names} parents={sorted(item.parent_refs)}"
    )


def _today_window() -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now + dt.timedelta(minutes=5)


def _pick_scratch(size: int, used: set[str]) -> Path | None:
    """Archivo grande ya asignado donde volcar sin pedir clústeres libres."""
    temp = Path(os.environ.get("TEMP", r"C:\Users\jeissonsegura\AppData\Local\Temp"))
    candidates: list[Path] = []
    for d in temp.glob("recsess_*"):
        for p in d.iterdir():
            if p.is_file() and str(p) not in used:
                candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    for p in candidates:
        if p.stat().st_size >= size:
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--letter", default="C")
    parser.add_argument(
        "--out",
        default=str(Path.home() / "RecoveredMeeting" / "2026-09-09"),
    )
    parser.add_argument("--log", default="")
    parser.add_argument(
        "--dump",
        default="",
        help="IDs MFT separados por coma para volcar sin escanear todo",
    )
    args = parser.parse_args()
    if not args.scan and not args.copy:
        args.scan = True

    out_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        out_lines.append(msg)

    start, end = _today_window()
    log(f"ventana {start} .. {end}")
    try:
        handle = _open_volume(args.letter)
    except OSError as exc:
        log(f"ERROR_OPEN {exc}")
        log("NEED_ADMIN")
        if args.log:
            Path(args.log).write_text("\n".join(out_lines), encoding="utf-8")
        return 2
    try:
        boot = parse_boot(_read_at(handle, 0, 512))
        log(
            f"NTFS cluster={boot.cluster_size} rec={boot.record_size} mft_lcn={boot.mft_lcn}"
        )
        mft_runs = load_mft_runs(handle, boot)
        if args.dump:
            for raw_id in args.dump.split(","):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                idx = int(raw_id)
                try:
                    rec = mft_record_at(handle, boot, mft_runs, idx)
                    log(describe_record(rec, boot.record_size, idx))
                except Exception as exc:
                    log(f"dump FAIL MFT#{idx}: {exc}")
            if args.log:
                Path(args.log).parent.mkdir(parents=True, exist_ok=True)
                Path(args.log).write_text("\n".join(out_lines), encoding="utf-8")
            return 0
        log("escaneando MFT (varios minutos)...")
        mft_runs = load_mft_runs(handle, boot)
        found = scan(handle, boot, mft_runs, start, end)
        uniq: dict[int, FoundFile] = {}
        for item in found:
            uniq[item.mft_ref] = item
        items = list(uniq.values())
        for item in items:
            try:
                resolve_item(handle, boot, mft_runs, item)
            except Exception as exc:
                log(f"resolve FAIL MFT#{item.mft_ref}: {exc}")
        items.sort(key=lambda x: ((x.modified or x.created or dt.datetime.min), x.mft_ref))
        log(f"candidatos={len(items)}")
        for item in items:
            extra = ",".join(str(x) for x in sorted(item.extra_refs))
            log(_fmt(item) + f" extra=[{extra}] runs={len(item.data_runs)}")
            if item.data_runs and item.data_runs[0] and item.data_runs[0][0] == "__resident_bytes__":
                preview = item.data_runs[0][1][:300]
                try:
                    log("  resident: " + preview.decode("utf-8", "replace"))
                except Exception:
                    log("  resident hex: " + preview[:80].hex())

        session_parents = {
            it.mft_ref
            for it in items
            if it.is_dir and any(n.startswith("recsess_") for n in it.names)
            and (_in_window(it.created, start, end) or _in_window(it.modified, start, end))
        }
        # Sesión de hoy ya identificada en el primer pase.
        session_parents.add(1076264)
        log(f"session_parents={sorted(session_parents)}")
        today_files = [
            it
            for it in items
            if not it.is_dir
            and not it.in_use
            and (
                it.parent_refs & session_parents
                or _in_window(it.created, start, end)
                or _in_window(it.modified, start, end)
            )
        ]
        today_files.sort(key=lambda x: x.size, reverse=True)
        log(f"borrados_hoy={len(today_files)}")
        if args.copy and today_files:
            dest_root = Path(args.out)
            dest_root.mkdir(parents=True, exist_ok=True)
            used_scratch: set[str] = set()
            for it in today_files:
                name = it.names[0] if it.names else f"mft_{it.mft_ref}.bin"
                dest = dest_root / f"{it.mft_ref}_{name}"
                scratch = None
                if it.size > 8 * 1024 * 1024:
                    scratch = _pick_scratch(it.size, used_scratch)
                    if scratch is not None:
                        used_scratch.add(str(scratch))
                log(f"copiando {name} ({it.size} bytes) -> {dest} scratch={scratch}")
                if it.size <= 0:
                    log(f"SKIP {name}: tamaño 0 tras resolver atributos (MFT extra incompleta)")
                    continue
                if it.size > 8 * 1024 * 1024 and scratch is None:
                    log(f"SKIP {name}: no hay archivo-scratch suficientemente grande; no se copiará a clústeres libres")
                    continue
                try:
                    copy_file(handle, boot, it, dest, overwrite_target=scratch)
                    log(f"OK {dest} ({dest.stat().st_size} bytes)")
                except Exception as exc:
                    log(f"FAIL {name}: {exc}")
        elif args.copy:
            log("Nada borrado de hoy para copiar.")
    finally:
        kernel32.CloseHandle(handle)
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        Path(args.log).write_text("\n".join(out_lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
