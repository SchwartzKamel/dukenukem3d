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

    for filename, data in files_dict.items():
        name = filename.upper().encode("ascii")
        if len(name) > 12:
            raise ValueError(f"Filename too long (max 12 chars): {filename}")
        name = name.ljust(12, b"\x00")
        directory += name + struct.pack("<I", len(data))
        all_data += data

    return header + directory + all_data
