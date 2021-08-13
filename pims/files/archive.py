import shutil
import sys

from functools import lru_cache

from pims.api.exceptions import NoMatchingFormatProblem
from pims.files.file import Path


class ArchiveError(OSError):
    pass


class ArchiveFormat:
    def __init__(self, name, description, match):
        self.name = name
        self.description = description
        self.match = match

    def get_identifier(self, uppercase=True):
        if uppercase:
            return self.name.upper()
        return self.name

    def get_name(self):
        return self.get_identifier(False)

    def get_remarks(self):
        return self.description


def zip_match(signature):
    return (len(signature) > 3 and
            signature[0] == 0x50 and signature[1] == 0x4B and
            (signature[2] == 0x3 or signature[2] == 0x5 or
             signature[2] == 0x7) and
            (signature[3] == 0x4 or signature[3] == 0x6 or
             signature[3] == 0x8))


def tar_match(signature):
    return (len(signature) > 261 and
            signature[257] == 0x75 and
            signature[258] == 0x73 and
            signature[259] == 0x74 and
            signature[260] == 0x61 and
            signature[261] == 0x72)


def gztar_match(signature):
    return (len(signature) > 2 and
            signature[0] == 0x1F and
            signature[1] == 0x8B and
            signature[2] == 0x8)


def bztar_match(signature):
    return (len(signature) > 2 and
            signature[0] == 0x42 and
            signature[1] == 0x5A and
            signature[2] == 0x68)


def xztar_match(signature):
    return (len(signature) > 5 and
            signature[0] == 0xFD and
            signature[1] == 0x37 and
            signature[2] == 0x7A and
            signature[3] == 0x58 and
            signature[4] == 0x5A and
            signature[5] == 0x00)


@lru_cache
def _build_archive_format_list():
    formats = []
    extensions = shutil.get_archive_formats()
    for name, description in extensions:
        match_fn_name = f"{name}_match"
        match = getattr(sys.modules[__name__], match_fn_name, None)
        if match is not None:
            formats.append(ArchiveFormat(name, description, match))
    return formats


ARCHIVE_FORMATS = _build_archive_format_list()


class Archive(Path):
    def __init__(self, *pathsegments, format=None):
        super().__init__(pathsegments)

        _format = None
        if format:
            _format = format
        else:
            signature = self.signature()
            for possible_format in ARCHIVE_FORMATS:
                if possible_format.match(signature):
                    _format = possible_format
                    break

        if _format is None:
            raise NoMatchingFormatProblem(self)
        else:
            self._format = _format

    def extract(self, path: Path):
        if path.exists() and not path.is_dir():
            raise ArchiveError(f"{self} cannot be extracted in {path} because "
                               f"it already exists or it is not a directory")

        try:
            shutil.unpack_archive(self.absolute(), path, self._format.name)
        except shutil.ReadError as e:
            raise ArchiveError(str(e))

        # TODO: clean unpacked directory (.DS_STORE)

    @classmethod
    def from_path(cls, path):
        try:
            return cls(path)
        except NoMatchingFormatProblem:
            return None

    @property
    def format(self):
        return self._format