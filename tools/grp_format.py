# SPDX-License-Identifier: GPL-2.0-or-later
"""GRP file packer for Duke Nukem 3D / BUILD engine.

GRP format:
  - 12 bytes: "KenSilverman" magic
  - 4 bytes: number of files (uint32 LE)
  - For each file: 12 bytes filename (null-padded) + 4 bytes size (uint32 LE)
  - All file data concatenated in directory order
"""

import struct


def create_grp(files_dict):
    """Pack files into a GRP archive.

    Args:
        files_dict: dict mapping uppercase 8.3 filenames to bytes data.

    Returns:
        bytes: Complete GRP file content.
    """
    magic = b"KenSilverman"
    num_files = len(files_dict)

    header = magic + struct.pack("<I", num_files)

    directory = b""
    all_data = b""

    # Sort files for deterministic output
    for filename in sorted(files_dict.keys()):
        data = files_dict[filename]
        name = filename.upper().encode("ascii")
        if len(name) > 12:
            raise ValueError(f"Filename too long (max 12 chars): {filename}")
        name = name.ljust(12, b"\x00")
        directory += name + struct.pack("<I", len(data))
        all_data += data

    return header + directory + all_data


def read_grp(data):
    """Parse a GRP archive into a dict ``{NAME: bytes}`` — the inverse of
    :func:`create_grp`.

    Because :func:`create_grp` sorts its keys deterministically, the round trip
    ``create_grp(read_grp(g)) == g`` holds byte-for-byte for any ``g`` it produced.
    That invariant makes a *surgical* CON-only repack safe (see
    docs/plans/2026-06-15_GRP-CON-REPACK_SPEC.md).

    Raises ValueError on a bad/truncated archive.
    """
    if len(data) < 16 or data[:12] != b"KenSilverman":
        raise ValueError("not a GRP archive (missing 'KenSilverman' magic)")
    num_files = struct.unpack("<I", data[12:16])[0]
    dir_start = 16
    data_start = dir_start + num_files * 16
    if len(data) < data_start:
        raise ValueError("GRP directory is truncated")
    files = {}
    off = data_start
    for i in range(num_files):
        e = dir_start + i * 16
        name = data[e:e + 12].split(b"\x00")[0].decode("ascii", "replace")
        size = struct.unpack("<I", data[e + 12:e + 16])[0]
        if off + size > len(data):
            raise ValueError(f"GRP data truncated reading {name!r}")
        files[name] = data[off:off + size]
        off += size
    return files


def replace_files(grp_data, overrides):
    """Return a new GRP with the ``{NAME: bytes}`` ``overrides`` swapped in place,
    every other entry byte-identical.

    Surgical replace only — each override name must already exist in the archive
    (matched case-insensitively; GRP entries are uppercase). Raises KeyError for an
    unknown name (this is not a general add/remove editor).
    """
    files = read_grp(grp_data)
    existing = {k.upper(): k for k in files}
    for name, payload in overrides.items():
        key = name.upper()
        if key not in existing:
            raise KeyError(f"{name!r} is not in the GRP (replace_files does not add entries)")
        files[existing[key]] = payload
    return create_grp(files)
