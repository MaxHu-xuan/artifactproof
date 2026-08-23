# SPDX-License-Identifier: Apache-2.0

"""Stable, streaming SHA-256 file hashing."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

from .errors import ArtifactChangedError, InputError


PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class FileDigest:
    """A non-secret logical name and a content digest."""

    name: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _safe_name(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 255:
        raise InputError("a logical file name is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise InputError("a logical file name is invalid")
    return name


def _identity(file_stat: os.stat_result) -> tuple:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )


def digest_file(path: PathLike, name: Optional[str] = None) -> FileDigest:
    """Hash a regular file and reject detectable mutation during the read."""

    file_path = Path(path)
    logical_name = _safe_name(name if name is not None else file_path.name)
    try:
        path_stat_before = file_path.stat()
        if not stat.S_ISREG(path_stat_before.st_mode):
            raise InputError("an input is not a regular file")

        hasher = hashlib.sha256()
        with file_path.open("rb") as stream:
            fd_stat_before = os.fstat(stream.fileno())
            if _identity(fd_stat_before) != _identity(path_stat_before):
                raise ArtifactChangedError()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
            fd_stat_after = os.fstat(stream.fileno())

        path_stat_after = file_path.stat()
    except ArtifactChangedError:
        raise
    except InputError:
        raise
    except (OSError, ValueError) as exc:
        raise InputError("an input file is not readable") from exc

    if (
        _identity(path_stat_before) != _identity(fd_stat_before)
        or _identity(fd_stat_before) != _identity(fd_stat_after)
        or _identity(fd_stat_after) != _identity(path_stat_after)
    ):
        raise ArtifactChangedError()

    return FileDigest(logical_name, hasher.hexdigest(), fd_stat_after.st_size)
