#!/usr/bin/env python3

# on404 handler
# sends custom response instead of the default 404 page

import datetime as dt
from enum import Enum
from io import BufferedReader
import json
from collections import namedtuple
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import quote
import re
import struct


# TODO: DON'T FORGET HOW FILEKEYS ARE HANDLED BEFORE I WRITE IT DOWN
# TODO: REVIEW ALL THE tx404, tx403, return "true", return "false", return "" ONE MORE TIME
# TODO: REVIEW ALL THE is_ps4() and cli.uname == '*' and rem.lower().endswith('.pkg') combinations; maybe introduce some functionss
# TODO: REMOVE DEFUALT PS4_IP VALUE
# TODO: RENAME EVERYTHING TB -> V
# TODO: JS; IT'S STILL DIRTY
# TODO: TEST CP_HOST
# TODO: REMOVE OR CONFIGURE BASIC AUTH FOR FPKGI SERVER
# TODO: ADD SECONDARY PS4 IP ADDRESSES TO ENABLE SAME ACCESS LEVEL FOR FPKGI FOR DIFFERENT CONSOLES??? gh issue
# TODO: ADD MAPPING UNAME:PS4IP??? just create gh issue and do it if someone uses this software and thinks they need this feature

PAYLOAD_CONTENT_ID_SIZE = 0x30
PAYLOAD_CONTENT_URL_SIZE = 0x800
PAYLOAD_CONTENT_NAME_SIZE = 0x259
PAYLOAD_ICON_URL_SIZE = 0x800
PAYLOAD_PACKAGE_TYPE_SIZE = 0x15
PAYLOAD_PACKAGE_SIZE_SIZE = 0x8

PS4_IP = os.getenv('FPKGTB_PS4_IP', '192.168.31.125')
if not PS4_IP:
    raise Exception('Put your PS4 IP addres into environment variable FPKGTB_PS4_IP!')
CP_HOST = os.getenv('FPKGTB_CP_HOST')
if CP_HOST:
    CP_HOST = CP_HOST.rstrip('/').split('://')
    if len(CP_HOST) != 2:
        raise Exception(f'Invalid FPKGTB_CP_HOST: {'://'.join(CP_HOST)}; valid examples: http://192.168.1.71:3923, https://party.mydomain.fun')

SEND_USERS = os.getenv('FPKGTB_SEND_USERS', '*').replace(' ', '').split(',')

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
DOWNLOAD_PREFIX = COMMON_VFS_PREFIX + 'dl/'
COVER_POSTFIX = '.png'
JSON_VFS_PATH_PATTERN = re.compile(rf'^{COMMON_VFS_PREFIX}(?:all|(?P<category>DLC|games|apps|PS2|updates|homebrew)).json$')


def main(*args, **kwargs):
    # called as thumb extractor
    if len(args) == 1 and isinstance(args[0], str) and kwargs:
        return handle_thumb_extract(*args, **kwargs)

    # called externally as tag extractor
    # see if __name__ in the end
    if not args and not kwargs and __name__ == '__main__':
        exit(handle_mtag(Path(sys.argv[1])))

    if not (
        len(args) == 3
        and args[0].__class__.__name__ == 'HttpCli'
        and args[1].__class__.__name__ == 'VFS'
        and isinstance(args[2], str)
    ):
        raise Exception(f'Unknown args: {args=!r}, {kwargs=!r}')

    # called as on404/on403 handler
    cli, vn, rem = args
    if not rem.startswith(COMMON_VFS_PREFIX):
        if cli.vpath == '':
            return 'home'
        return ''

    if rem == SCRIPT_VFS_PATH:
        cli.reply(SCRIPT_JS, 200, "text/javascript")
        return 'false'

    if rem == STYLE_VFS_PATH:
        cli.reply(STYLE_CSS, 200, "text/css")
        return 'false'

    if rem.startswith(COVER_VFS_PREFIX):
        return handle_cover(cli, vn, rem[len(COVER_VFS_PREFIX):-len(COVER_POSTFIX)])

    if rem.startswith(SENDER_VFS_PREFIX):
        return handle_send(cli, vn, rem[len(SENDER_VFS_PREFIX):])
    
    if rem.startswith(DOWNLOAD_PREFIX):
        return handle_download(cli, vn, rem[len(DOWNLOAD_PREFIX):])

    match = JSON_VFS_PATH_PATTERN.match(rem)
    if match:
        return handle_json(cli, vn, match.group('category') or None)

    return ''

###### /Dispatching ######


###### Tags extraction ######

def handle_mtag(path: Path):
    """
    extract FPKG metadata to show it in copyparty file list view
    mutagen or ffmpeg required
    copyparty options:
        -e2dsa
        -e2ts
        -mtp type,category,title,title_id,content_id,app_ver,version,system_ver=an,epkg,c1,f,./fpkg_toolbox.py
        -mte +type,category,title,title_id,content_id,app_ver,version,system_ver

    https://github.com/9001/copyparty#file-parser-plugins
    """
    if path.suffix.lower() != '.pkg':
        print('{}')
        return 1
    with PkgFile(path) as pkg:
        if not pkg.is_valid:
            print('{}')
            return 1
        psfo = pkg.extract_param_sfo()

    # TODO: unduplicate category stuff
    _BACKPORT_FILENAME_PATTERN = re.compile(r'BACKPORT|FIX[4567]|(?<![A-Z])BP(?![A-Z])|CYB1K', re.IGNORECASE)
    _PS2_PATTERN = re.compile(r"S[CL][PUE][SMD]")

    params = {
        name.lower(): value
        for name, value in psfo.items()
        if name in {'CATEGORY', 'TITLE', 'TITLE_ID', 'CONTENT_ID', 'APP_VER', 'VERSION', 'SYSTEM_VER'}
    }
    cat = params['category']
    params['type'] = None
    if cat:
        if cat == 'ac':
            params['type'] = 'dlc'
        elif cat in ['bd', 'gc', 'gd']:
            params['type'] = 'game'
        elif cat[:2] == 'gd':
            params['type'] = 'ps2' if cat[2] in 'oO0' else 'app'
        elif cat[:2] == 'gp':
            params['type'] = 'update'

    if _PS2_PATTERN.match(params['title_id']):
        params['type'] = 'ps2'
    elif _BACKPORT_FILENAME_PATTERN.search(path.stem):
        params['type'] = 'backport'

    print(json.dumps(params, indent=4))
    return 0

###### /Tags extraction ######


###### Cover image ######

def handle_thumb_extract(abspath, **kwargs):
    """
    cover images for copyparty web ui
    ffmpeg (wtih jxl or webp support) or PIL or VIPS needed
    copyparty options:
        --th-extract pkg=./fpkg-toolbox.py

    https://copyparty.eu/cli/#thumb-ex-help-page
    """
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
    """
    cover images by url for fpkgi server and fpkg sender
    copyparty options:
        --on404 ./fpkg_toolbox.py
        --on403 ./fpkg_toolbox.py
    """
    if not is_ps4(cli) and not ACCESS_PERMISSIONS.can_access(cli.uname, vn, rem):
        cli.tx_404(is_403=True)
        return 'false'

    with PkgFile(vn.canonical(rem)) as pkg:
        image = pkg.extract_cover_image()

    if image is None:
        cli.tx_404()
        return 'false'

    cli.reply(image, 200, 'image/png')
    return 'false'

###### /Cover image ######


###### FPKG and payload sender ######

def handle_send(cli, vn, rem):
    """
    send payload to PS4
    for FPKG: generate installation payload and send it

    copyparty options:
        --on404 ./fpkg_toolbox.py
        --on403 ./fpkg_toolbox.py
    """
    if not can_send(cli.uname):
        cli.reply(
            b'you are not allowed to send payloads and packages from this server',
            403,
            'text/plain'
        )
        return 'false'

    if not SEND_PERMISSIONS.can_access(cli.uname, vn, rem):
        cli.tx_404(is_403=True)
        return 'false'

    realpath = Path(vn.realpath, rem).resolve()
    if not realpath.is_file():
        cli.tx_404()
        return 'false'
    suffix = realpath.suffix.lower()
    is_pkg = suffix == '.pkg'
    is_payload = suffix == '.bin' or suffix == '.elf'
    
    if not is_payload and not is_pkg:
        cli.reply(b'looks like it is not a .pkg, .bin or .elf file', 400, 'text/plain')
        return "false"
    
    if is_payload:
        with socket.create_connection((PS4_IP, '9090')) as con:
            with open(realpath, 'rb') as f:
                con.sendfile(f)
        cli.reply(b'sent', 200, 'text/plain')
        time.sleep(0.4)
        return "false"

    with PkgFile(realpath) as pkg:
        if not pkg.is_valid:
            cli.reply(b'invalid PKG file', 400, 'text/plain')
            return("false")
        param_sfo = pkg.extract_param_sfo()

    base_url = get_base_url(cli, swaphost=True)
    params = {}
    params['content_name'] = param_sfo.get('TITLE', 'Content')
    params['content_id'] = param_sfo['CONTENT_ID']
    params['package_type'] = 'PS4' + param_sfo.get('CATEGORY', 'GD').upper()
    params['content_url'] = base_url + urlpath([vn.vpath, DOWNLOAD_PREFIX], rem)
    # https://github.com/OSM-Made/PS4-Notify
    params['icon_url'] = 'cxml://psnotification/tex_default_icon_download'
    params['package_size'] = pkg.size
    cli.log(f'{params=}')
    if pkg.has_cover_image():
        params['icon_url'] = (base_url + urlpath([vn.vpath, COVER_VFS_PREFIX], rem, COVER_POSTFIX))
    
    with socket.create_connection((PS4_IP, '9090')) as con:
        con.sendall(fill_template(**params))
    cli.reply(b'sent', 200, 'text/plain')
    time.sleep(0.4)
    return "false"


def can_send(uname):
    allow_authorized = False
    users = []
    for user in SEND_USERS:
        if user == '*':             # anyone allowed, default
            return True
        if user == '@':             # only authorized allowd
            allow_authorized = True
        if user == uname:           # explicitly allowed
            return True
        if user == '-' + uname:     # forbidden
            return False
    return allow_authorized and uname != '*'


def fill_template(content_id, content_url, content_name, icon_url, package_type, package_size):
    p = bytearray(PAYLOAD_TEMPLATE)
    items = [
        (content_id, PAYLOAD_CONTENT_ID_START, PAYLOAD_CONTENT_ID_SIZE),
        (content_url, PAYLOAD_CONTENT_URL_START, PAYLOAD_CONTENT_URL_SIZE),
        (content_name, PAYLOAD_CONTENT_NAME_START, PAYLOAD_CONTENT_NAME_SIZE),
        (icon_url, PAYLOAD_ICON_URL_START, PAYLOAD_ICON_URL_SIZE),
        (package_type, PAYLOAD_PACKAGE_TYPE_START, PAYLOAD_PACKAGE_TYPE_SIZE),
    ]
    for value, start, maxsize in items:
        value = bytes(value, 'utf-8', 'replace')[:maxsize - 1] + b'\0'
        p[start:start+len(value)] = value

    package_size = package_size.to_bytes(8, "little")
    package_size = package_size[:PAYLOAD_PACKAGE_SIZE_SIZE]
    p[PAYLOAD_PACKAGE_SIZE_START:PAYLOAD_PACKAGE_SIZE_START+len(package_size)]
    return p

###### /FPKG and payload sender ######



###### Special download path ######

def handle_download(cli, vn, rem):
    """
    special url path for PS4 to download packages
    allows special handling of PS4_IP

    this exists for two reasons:
    - to bypass copyparty's filekeys (I could do something smarter but why) (my PS4 didn't like urls with `?k=123456` query, maybe I just didn't try hard enough)
    - to allow easy access to all pkg files with basic setup (just put in handlers and you can send any pkg)
    see https://github.com/9001/copyparty/issues/1619
    """
    print("HANDLE_DOWNLOAD")
    print(f"{is_ps4(cli)=}")
    print(f"{rem.lower().endswith('.pkg')=}")
    print(f"{vn.canonical(rem)=}")
    if not is_ps4(cli) or not rem.lower().endswith('.pkg'):
        return ''
    cli.tx_file('oh_g', vn.canonical(rem))
    return 'false'

###### /Special download path ######


###### FPKGi server ######

def handle_json(cli, vn, category):
    """
    serve FPKGi JSON files to install stored games/apps from ItsJokerZz's FPKGi app

    https://github.com/ItsJokerZz/FPKGi
    """
    cached = Cache(cli.uname, cli.ip, vn.vpath)
    packages = cached.data
    if packages is None:
        packages = get_all_packages(cli, vn)
        cached.data = packages

    if category is not None:
        packages = {url: value for url, value in packages.items() if value["category"] == category}

    response_body = json.dumps({"DATA": packages}).encode("utf-8")

    cli.reply(response_body, 200, "application/json")
    return 'false'


def get_all_packages(cli, vn):
    base_url = get_base_url(cli, bauth=True)
    dl_prefix = DOWNLOAD_PREFIX if is_ps4(cli) else ''

    # bypass permission check for main PS4 in basic setup when there is no dedicated PS4 account (low performance, zero setup)
    # otherwise return packages based on permissions (e.g. user can exclude some dirs from serving to FPKGi)
    perms = YOLO_PERMISSIONS if cli.uname == '*' and is_ps4(cli) else ACCESS_PERMISSIONS
    packages = {}
    vols = {
        vp: vfs
        for vp, vfs in cli.asrv.vfs.all_vols.items()
        if vp.startswith(vn.vpath) and perms.can_access(cli.uname, vfs)
    }
    print(f'VOLSVOLS {set(vols)=}')
    for vp2, vn2 in vols.items():
        print('\n\n')
        print(f'VFS {vp2=}')
        for vn3, rem3, _rel, fsroot, files, _rdirs, _vvirt in vn2.walk(
            '', '', [], cli.uname, perms.permissions, 0, False, False, False
        ):
            for file_name, stat in files:
                if file_name[-4:].lower() != '.pkg':
                    continue
                abspath = Path(fsroot, file_name).resolve()
                if abspath.suffix.lower() != '.pkg' or abspath in packages:
                    continue
                with PkgFile(abspath) as pkg:
                    if not pkg.is_valid:
                        continue
                    param_sfo = pkg.extract_param_sfo()

                # convert to vpath relative to original request vn
                # in case handlers are disabled in subvolumes
                rem = ndp(vn3.vpath)[len(ndp(vn.vpath)):] + ndp(rem3) + nfp(file_name)

                url = base_url + urlpath([vn.vpath, dl_prefix], rem)
                icon_url = (base_url + urlpath(
                    [vn.vpath, COVER_VFS_PREFIX],
                    rem, COVER_POSTFIX
                )) if pkg.has_cover_image() else None
                packages[abspath] = (
                    url,
                    format_pkg_params(param_sfo, file_name[:-4], icon_url, stat.st_size)
                )
    return dict(packages.values())


class Cache:
    _caches = {}

    def __new__(cls, username, ip, vfs_root):
        cached = cls._caches.get((username, ip, vfs_root))
        if cached is not None and cached.is_valid:
            return cached

        new_instance = super().__new__(cls)
        new_instance.username = username
        new_instance.ip = ip
        new_instance.vfs_root = vfs_root
        new_instance.cached_at = dt.datetime.min
        new_instance._data = {}

        cls._caches[(username, ip, vfs_root)] = new_instance

        return new_instance

    @property
    def data(self):
        if self.is_valid:
            print(f'Got packages from cache for user "{self.username}" ip "{self.ip}" vpath "{self.vfs_root}"')
            return self._data
        print(f'No packages from cache for user "{self.username}" ip "{self.ip}" vpath "{self.vfs_root}"')
        return None

    @data.setter
    def data(self, data):
        print(f'Caching packages for user "{self.username}" ip "{self.ip}" vpath "{self.vfs_root}"')
        self._data = data
        self.cached_at = dt.datetime.now()

    @property
    def is_valid(self):
        return self.cached_at >= dt.datetime.now() - dt.timedelta(seconds=10)


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

###### /FPKGi server ######


###### Common utils ######

_ipnorm = None
def is_ps4(cli):
    global _ipnorm
    if not _ipnorm:
        module = sys.modules.get(cli.__class__.__module__)
        _ipnorm = getattr(module, 'ipnorm', lambda x: x)
    return _ipnorm(cli.ip) == _ipnorm(PS4_IP)


def ndp(dpath):
    """
    normalize directory path
    if it is root path ('' or '/') it must be ''
    otherwise:
    directory path should not start with '/'
    directory path should end with '/'
    so concatenating dir1 + dir2 + dir3 is predictable:
    - directories are separated by '/'
    - no '/' repeated
    """
    dpath = dpath.strip('/')
    return dpath + '/' if dpath else dpath


def nfp(fpath):
    """
    normalize file path
    file path should not start nor end with '/'
    so concatenating dir1 + dir2 + file3 is predictable:
    - directories and files are separated by '/'
    - no '/' repeated
    """
    return fpath.strip('/')


def urlpath(dirs, fp=None, *suf):
    path = ''.join(ndp(dir) for dir in dirs)
    if fp is not None:
        path += nfp(fp) + ''.join(suf)
    return quote(path)


def get_base_url(cli, *, bauth=False, swaphost=False):
    if swaphost and CP_HOST:
        protocol, host = CP_HOST
    else:
        protocol = "https" if cli.is_https else "http"
        host = cli.host

    basic_auth=''
    if bauth and (cli.uname != '*' or cli.pw):
        basic_auth = f'{cli.uname}:{cli.pw}@'
    
    return f"{protocol}://{basic_auth}{host}{cli.args.SRS}"


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

    def can_access(self, uname, vn, rem: Path | str = ''):
        """Checks if specified user can access specified path in specified VFS"""
        existing_permission = vn.can_access(str(rem), uname=uname)
        return self.check(existing_permission)


# any of r/g/G/h is fine
ACCESS_PERMISSIONS = PermSet(
    Permission(read=True),
    Permission(get=True),
    Permission(upget=True),
    Permission(html=True),
)
SEND_PERMISSIONS = PermSet(Permission(read=True))
YOLO_PERMISSIONS = PermSet(Permission())

###### /Common utils ######


###### FPKG stuff ######

class PkgFile(object):
    """
    this almost-file-like class extracts data from FPKG files
    based on psdevwiki and some other code (can't remember, probably maxton's LibOrbisPkg)

    https://www.psdevwiki.com/ps4/PKG_files
    """

    ENTRY_ID_PARAM_SFO = 0x1000
    ENTRY_ID_ICON0_PNG = 0x1200
    ENTRY_ID_PIC0_PNG = 0x1220

    SFO_TYPE_INT = 0x404
    SFO_TYPE_UTF8_NULL_TERMINATED = 0x204
    SFO_TYPE_UTF8_NO_NULL = 0x04

    REQUIRED_PARAMS = {'TITLE_ID', 'TITLE', 'CONTENT_ID', 'VERSION', 'APP_VER', 'SYSTEM_VER', 'CATEGORY', 'EMU_VERSION', 'CONTENT_VER'}

    def __init__(self, filepath: str | Path):
        self.size = os.stat(filepath).st_size
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


if __name__ == '__main__':
    # running as mtp – tag extractor
    main()
