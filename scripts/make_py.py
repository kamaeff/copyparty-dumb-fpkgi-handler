import base64
import os
import re

try:
    from rjsmin import jsmin
except ImportError:
    # not too brave to do it myself lol
    jsmin = lambda s: s

# at some point it will hurt
# but hopefully I either reject minifiers or switch to something by that moment
def cssmin(s):
    return re.sub(r'(?:\s|/\*.*?\*/)+', ' ', s).replace(': ', ':').replace('; ', ';').strip()


with open('src/fpkg_toolbox.py', 'rt') as py_f:
    py_s = py_f.read()

with open('build/payload.bin', 'rb') as payload_f:
    payload_b = payload_f.read()

with open('src/web/style.css', 'rt') as css_f:
    css_s = css_f.read()

with open('src/web/script.js', 'rt') as js_f:
    js_s = js_f.read()

py_s = py_s.replace('\nPAYLOAD_TEMPLATE = None', f'''
import base64
PAYLOAD_TEMPLATE = base64.b64decode({base64.b64encode(payload_b)!r})''', count=1)

prefixes = {
    "CONTENT_ID": b"{{ PACKAGE_CONTENT_ID }}",
    "CONTENT_URL": b"{{ PACKAGE_CONTENT_URL }}",
    "CONTENT_NAME": b"{{ PACKAGE_CONTENT_NAME }}",
    "ICON_URL": b"{{ PACKAGE_ICON_URL }}",
    "PACKAGE_TYPE": b"{{ PACKAGE_TYPE }}",
    "PACKAGE_SIZE": (0x123456789ABCDEFF).to_bytes(8, 'little'),
}

for k, v in prefixes.items():
    py_s = py_s.replace(f'\nPAYLOAD_{k}_START = None', f'\nPAYLOAD_{k}_START = 0x{payload_b.index(v):X}', count=1)

py_s = py_s.replace('\nSTYLE_CSS = None', '\nSTYLE_CSS = ' + repr(bytes(cssmin(css_s), 'utf8')), count=1)

py_s = py_s.replace('\nSCRIPT_JS = None', '\nSCRIPT_JS = ' + repr(bytes(jsmin(js_s), 'utf8')), count=1)

with open('build/fpkg_toolbox.py', 'wt') as out:
    out.write(py_s)
os.chmod('build/fpkg_toolbox.py', 0o755)
print('built build/fpkg_toolbox.py')
