# on404 handler
# sends custom response instead of the default 404 page

import datetime as dt
from enum import Enum
from io import BufferedReader
import json
from collections import namedtuple
from pathlib import Path
from urllib.parse import quote
import re
import struct



###### Build stuff ######

PAYLOAD_TEMPLATE = None
PAYLOAD_CONTENT_ID_START = None
PAYLOAD_CONTENT_URL_START = None
PAYLOAD_CONTENT_NAME_START = None
PAYLOAD_ICON_URL_START = None
PAYLOAD_PACKAGE_TYPE_START = None
PAYLOAD_PACKAGE_SIZE_START = None

assert PAYLOAD_TEMPLATE is not None

SCRIPT_JS = None
assert SCRIPT_JS is not None

STYLE_CSS = None
assert STYLE_CSS is not None

###### /Build stuff ######


###### Dispatching ######

COMMON_VFS_PREFIX = '__fpkgtb/'
SCRIPT_VFS_PATH = COMMON_VFS_PREFIX + 'script.js'
STYLE_VFS_PATH = COMMON_VFS_PREFIX + 'style.css'
COVER_VFS_PREFIX = COMMON_VFS_PREFIX + 'cover/'
SENDER_VFS_PREFIX = COMMON_VFS_PREFIX + 'sender/'
COVER_POSTFIX = '.png'
JSON_VFS_PATH_PATTERN = re.compile(rf'^{COMMON_VFS_PREFIX}(?:all|(?P<category>DLC|games|apps|PS2|updates|homebrew)).json$')


def main(*args, **kwargs):
    # called as thumb extractor
    if len(args) == 1 and isinstance(args[0], str) and kwargs:
        return handle_thumb_extract(*args, **kwargs)

    if not (
        len(args) == 3
        and args[0].__class__.__name__ == 'HttpCli'
        and args[1].__class__.__name__ == 'VFS'
        and isinstance(args[2], str)
    ):
        raise Exception(f'Unknown args: {args=!r}, {kwargs=!r}')

    # called as on404 handler
    cli, vn, rem = args
    if not rem.startswith(COMMON_VFS_PREFIX):
        return str(cli.tx_404())

    if rem == SCRIPT_VFS_PATH:
        cli.reply(SCRIPT_JS, 200, "text/javascript")
        return "true"

    if rem == STYLE_VFS_PATH:
        cli.reply(STYLE_CSS, 200, "text/css")
        return "true"

    if rem.startswith(COVER_VFS_PREFIX):
        return handle_cover(cli, vn, rem[len(COVER_VFS_PREFIX):-len(COVER_POSTFIX)])

    if rem.startswith(SENDER_VFS_PREFIX):
        return handle_send(cli, vn, rem[len(SENDER_VFS_PREFIX):])


    match = JSON_VFS_PATH_PATTERN.match(rem)
    if match is None:
        return str(cli.tx_404())

    return handle_json(cli, vn, match.group('category') or None)

###### /Dispatching ######



###### Main logic ######

def handle_send(cli, vn, rem):
    # check send.py on the desktop
    try:
        log = cli.log
        log('henlo from sendr')

        import random
        import time
        time.sleep(0.2 + random.random())
        if random.random() > 0.9:
            raise Exception('random error')
        cli.reply(bytes('sent', 'utf-8'), 200, "text/plain")
        return "true"
    except Exception as e:
        import traceback
        log(
            "FPKG extractor failed with an exception:\n" + traceback.format_exc()
        )
        msg = f'failed successfully\n{e!r}'
        cli.reply(bytes(msg, 'utf-8'), 400, "text/plain")
        return "false" # I don't remember what am I supposed to return

def handle_thumb_extract(abspath, **kwargs):
    f = None
    try:
        f = PkgFile(abspath)
        res = f.get_cover_location()
        if res is None:
            return None
        offset, length = res
        return 'png', f, offset, 0, length
    except Exception as e:
        if f:
            f.close()
        raise e

def handle_cover(cli, vn, rem):
    vfs_path = Path(vn.vpath, rem)

    if not REQUIRED_PERMISSIONS.can_access(vn, vfs_path, cli.uname):
        return str(cli.tx_404(is_403=True))

    with PkgFile(Path(vn.realpath, rem)) as pkg:
        image = pkg.extract_cover_image()

    if image is None:
        return str(cli.tx_404())

    cli.reply(image, 200, "image/png")
    return "true"


def handle_json(cli, vn, category):
    cached = Cache(cli.uname, vn.vpath)
    packages = cached.data
    if packages is None:
        packages = get_all_packages(cli, vn)
        cached.data = packages

    if category is not None:
        packages = {url: value for url, value in packages.items() if value["category"] == category}

    response_body = json.dumps({"DATA": packages}).encode("utf-8")

    cli.reply(response_body, 200, "application/json")
    return "true"


def get_all_packages(cli, vn):
    protocol = "https" if cli.is_https else "http"
    basic_auth=''
    if cli.uname != '*' or cli.pw:
        basic_auth = f'{cli.uname}:{cli.pw}@'
    base_url = f"{protocol}://{basic_auth}{cli.host}{cli.args.SRS}"

    packages = {}
    for walk_result in vn.walk('', '', [], cli.uname, REQUIRED_PERMISSIONS.permissions, 0, False, False, True):
        vfs_subdir = walk_result[2]
        fs_parent_dir = walk_result[3]
        files = (f for f in walk_result[4] if f[0].endswith('.pkg'))
        for file_name, stat in files:
            with PkgFile(Path(fs_parent_dir, file_name)) as pkg:
                param_sfo = pkg.extract_param_sfo()
                has_cover_image = pkg.has_cover_image()

            url = base_url + quote(f'{vn.vpath}/{vfs_subdir}/{file_name}')
            icon_url = (base_url + quote(f'{vn.vpath}/{COVER_VFS_PREFIX}{vfs_subdir}/{file_name}{COVER_POSTFIX}')) if has_cover_image else None
            packages[url] = format_pkg_params(param_sfo, file_name[:-4], icon_url, stat.st_size)

    return packages


class Cache:
    _caches = {}

    def __new__(cls, username, vfs_root):
        cached = cls._caches.get((username, vfs_root))
        if cached is not None and cached.is_valid:
            return cached

        new_instance = super().__new__(cls)
        new_instance.username = username
        new_instance.vfs_root = vfs_root
        new_instance.cached_at = dt.datetime.min
        new_instance._data = {}

        cls._caches[(username, vfs_root)] = new_instance

        return new_instance

    @property
    def data(self):
        if self.is_valid:
            print(f'Got packages from cache for user {self.username} vpath {self.vfs_root}')
            return self._data
        print(f'No packages from cache for user {self.username} vpath {self.vfs_root}')
        return None

    @data.setter
    def data(self, data):
        print(f'Caching packages for user {self.username} vpath {self.vfs_root}')
        self._data = data
        self.cached_at = dt.datetime.now()

    @property
    def is_valid(self):
        return self.cached_at >= dt.datetime.now() - dt.timedelta(seconds=10)

###### /Main logic ######


###### PKG to FPKGi data conversion ######

REGIONS = {
    'U': 'USA',
    'J': 'JAP',
    'E': 'EUR',
    'H': 'ASIA',
    # 'I': 'INT',
    # 'K': 'KOREA'
    'K': 'ASIA'
}
# CUSA is most common, catch it first
TITLE_ID_PATTERN = re.compile(r"(CUSA|[A-Z]{4})\d{5}")


def format_pkg_params(param_sfo: dict, file_name: str, cover_url: str, file_size: int):
    if param_sfo is None:
        return {
            'cover_url': None,
            'release': None,
            'size': file_size,
            'min_fw': None,
            'title_id': 'UNKNOWN',
            'region': None,
            'version': None,
            'category': 'homebrew',
            'name': f'BROKEN PKG FILE | {file_name}'
        }

    response = {
        'cover_url': cover_url,
        'release': None,
        'size': file_size,
        'min_fw': param_sfo.get('SYSTEM_VER'),
    }

    title_id = param_sfo.get('TITLE_ID')
    if title_id is None:
        match = TITLE_ID_PATTERN.search(file_name)
        title_id = match[0] if match else 'UNKNOWN'
    response['title_id'] = title_id

    content_id = param_sfo.get('CONTENT_ID')
    response['region'] = REGIONS.get(content_id[0].upper()) if content_id else None

    versions = []
    for param_name in 'APP_VER', 'VERSION', 'CONTENT_VER':
        version = param_sfo.get(param_name)
        if version:
            versions.append(f'{param_name[0]}{version}')
    response['version'] = '_'.join(versions) or None

    category = Category(param_sfo.get('CATEGORY'), title_id, file_name)
    response['category'] = category.fpkgi_category

    response['name'] = f'[{category.title_prefix}] {param_sfo.get('TITLE') or 'BROKEN PKG FILE'} | {file_name}'

    return response


class Category(object):
    _MAPPING = {
        'ac': 'DLC',
        'bd': 'games',
        'gc': 'games',
        'gd': 'games',
        'gda': 'apps',
        'gdb': 'apps',
        'gdc': 'apps',
        'gdd': 'apps',
        'gde': 'apps',
        'gdg': 'apps',
        'gdk': 'apps',
        'gdl': 'apps',
        'gdo': 'PS2',
        'gdO': 'PS2',
        'gd0': 'PS2',
        'gp': 'updates',
        'gpc': 'updates',
        'gpd': 'updates',
        'gpe': 'updates',
        'gpk': 'updates',
        'gpl': 'updates',
    }
    _TITLE_PREFIX = {
        'DLC': 'DLC',
        'games': 'Game',
        'apps': 'App',
        'PS2': 'PS2',
        'updates': 'Upd',
        'homebrew': 'HB'
    }
    _PS2_PATTERN = re.compile(r"S[CL][PUE][SMD]")
    _BACKPORT_FILENAME_PATTERN = re.compile(r'BACKPORT|FIX[4567]|(?<![A-Z])BP(?![A-Z])|CYB1K', re.IGNORECASE)

    def __init__(self, sfo_category, title_id, file_name):
        self.sfo_category = sfo_category

        if self._PS2_PATTERN.match(title_id):
            self.fpkgi_category = 'PS2'
        else:
            self.fpkgi_category = self._MAPPING.get(sfo_category, 'homebrew')

        if self._BACKPORT_FILENAME_PATTERN.search(file_name):
            self.title_prefix = 'BP'
        else:
            self.title_prefix = self._TITLE_PREFIX.get(self.fpkgi_category, self.fpkgi_category)

###### /PKG to FPKGi data conversion ######


###### Copyparty stuff ######

permission_fields = ('read', 'write', 'move', 'delete', 'get', 'upget', 'html', 'admin', 'dot')
Permission = namedtuple('Permission', permission_fields, defaults=(False,) * len(permission_fields))

class PermSet(object):
    def __init__(self, *permissions):
        self.permissions = permissions

    def check(self, requested_permission: Permission):
        """Checks if provided permission matches this PermSet"""
        for required_permission in self.permissions:
            for required, existing in zip(required_permission, requested_permission):
                # found mismatching option in currently checked required permission
                if required and not existing: break
            else:
                # no mismatching options at least for one permission in this PermSet
                return True
        return False

    def can_access(self, vfs, path, username):
        """Checks if spcified user can access specified path in specified VFS"""
        existing_permission = vfs.can_access(str(path), uname=username)
        return self.check(existing_permission)


# any of r/g/u/h/a is fine
REQUIRED_PERMISSIONS = PermSet(
    Permission(read=True),
    Permission(get=True),
    Permission(upget=True),
    Permission(html=True),
    Permission(admin=True),
)

###### /Copyparty stuff ######


###### FPKG stuff ######

class PkgFile(object):
    ENTRY_ID_PARAM_SFO = 0x1000
    ENTRY_ID_ICON0_PNG = 0x1200
    ENTRY_ID_PIC0_PNG = 0x1220

    SFO_TYPE_INT = 0x404
    SFO_TYPE_UTF8_NULL_TERMINATED = 0x204
    SFO_TYPE_UTF8_NO_NULL = 0x04

    REQUIRED_PARAMS = {'TITLE_ID', 'TITLE', 'CONTENT_ID', 'VERSION', 'APP_VER', 'SYSTEM_VER', 'CATEGORY', 'EMU_VERSION', 'SYSTEM_ROOT_VER', 'CONTENT_VER', 'PUBTOOLINFO'}

    def __init__(self, filepath: str | Path):
        try:
            self.file = open(filepath, 'rb')
            # check PKG file magic
            if self.seek(0).read_uint_be() != 0x7F434E54:
                raise Exception(f'Invalid PKG magic for file {filepath}')
            self.entries_locations = self._locate_entries()
            self.is_valid = True
        except Exception as e:
            print(e)
            self.close()
            self.is_valid = False
            self.entries_locations = {}


    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        return self.file.__exit__(*args, **kwargs)

    def close(self, *args, **kwargs):
        if hasattr(self, 'file') and self.file is not None:
            return self.file.close(*args, **kwargs)

    def _locate_entries(self):
        # read pkg header to get to metadata entries
        entry_count = self.seek(0x10).read_uint_be()
        entry_table_position = self.seek(0x18).read_uint_be()

        entries_locations = {}
        self.seek(entry_table_position)
        for _ in range(entry_count):
            entry_id = self.read_uint_be()
            entries_locations[entry_id] = self.seek(12,1).read_struct('>II')
            self.seek(8,1)
        return entries_locations

    def has_cover_image(self):
        return (
            self.ENTRY_ID_ICON0_PNG in self.entries_locations
            or
            self.ENTRY_ID_PIC0_PNG in self.entries_locations
        )

    def get_cover_location(self):
        return (
            self.entries_locations.get(self.ENTRY_ID_ICON0_PNG)
            or
            self.entries_locations.get(self.ENTRY_ID_PIC0_PNG)
        )

    def extract_cover_image(self):
        location = self.get_cover_location()
        if location is None:
            return None
        return self.seek(location[0]).read(location[1])

    def extract_param_sfo(self):
        location = self.entries_locations.get(self.ENTRY_ID_PARAM_SFO)
        if location is None:
            return None

        param_sfo_offset = location[0]
        self.seek(param_sfo_offset)

        # check SFO magic
        if self.read_uint_be() == 0x53434543:
            param_sfo_offset += 0x800

        if self.seek(param_sfo_offset).read_uint_be() != 0x00505346:
            return None

        params = dict.fromkeys(self.REQUIRED_PARAMS, None)

        # obtain params info
        key_table_offset = self.seek(param_sfo_offset + 8).read_int_le()
        data_table_offset = self.read_int_le()
        values_count = self.read_int_le()

        for idx in range(values_count):
            # get param entry info
            self.seek(idx * 0x10 + 0x14 + param_sfo_offset)
            key_offset, format_, length, _, data_offset = self.read_struct('<HHiiI')

            # get param name
            self.seek(param_sfo_offset + key_table_offset + key_offset)
            name = self.read_ascii()
            if name not in self.REQUIRED_PARAMS:
                continue

            # get param value
            self.seek(param_sfo_offset + data_table_offset + data_offset)
            if format_ == self.SFO_TYPE_INT:
                if name == 'SYSTEM_VER':
                    _, _, minor, major = self.read_struct('4b')
                    value = f'{major:x}.{minor:02x}'
                else:
                    value = self.read_int_le()
            elif format_ == self.SFO_TYPE_UTF8_NULL_TERMINATED:
                value = self.read_utf8(length - 1)
            elif format_ == self.SFO_TYPE_UTF8_NO_NULL:
                value = self.read_utf8(length)
            else:
                value = None

            params[name] = value

        return params

    def seek(self, offset, whence=0, /):
        self.file.seek(offset, whence)
        return self

    def read_struct(self, format):
        size = struct.calcsize(format)
        return struct.unpack(format, self.file.read(size))

    def read_uint_be(self):
        return self.read_struct('>I')[0]

    def read_int_le(self):
        return self.read_struct('<i')[0]

    def read_uint_le(self):
        return self.read_struct('<I')[0]

    def read_ushort_le(self):
        return self.read_struct('<H')[0]

    # no need to sacrifice readability I guess
    def read_ascii(self):
        res = bytearray()
        while True:
            byte = self.file.read(1)[0]
            if byte == 0:
                return res.decode('ASCII')
            res.append(byte)

    def read_utf8(self, length):
        if length > 0:
            return self.file.read(length).decode('utf-8')
        return None

    def __getattr__(self, name):
        return getattr(self.file, name)

###### /FPKG stuff ######


