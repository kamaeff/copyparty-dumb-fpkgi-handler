# on404 handler
# sends a custom response instead of the usual 404

import json
from pathlib import Path
import re
from urllib.parse import quote


def main(cli, vn, rem):
    if rem != '__FPKGi.json':
        return cli.tx_404()

    protocol = "https" if cli.is_https else "http"
    host = cli.host
    local_path_prefix = vn.realpath
    url_path_prefix = vn.vpath
    basic_auth=''
    if cli.uname != '*' or cli.pw:
        basic_auth = f'{cli.uname}:{cli.pw}@'

    response = {}
    for path in Path(local_path_prefix).rglob("*.pkg"):
        relative_url_path = path.relative_to(local_path_prefix).as_posix()
        url_path = quote(f"{url_path_prefix}/{relative_url_path}")
        url = f"{protocol}://{basic_auth}{host}/{url_path}"
        id_match = re.search(r"CUSA\d{5}", path.stem, flags=re.IGNORECASE)
        if id_match is not None:
            id_ = id_match[0]
        else:
            id_ = "UNKNOWN"
        response[url] = {
            "title_id": id_,
            "region": None,
            "name": path.stem,
            "version": None,
            "release": None,
            "size": path.stat().st_size,
            "min_fw": None,
            "cover_url": None,
        }

    response_body = json.dumps({"DATA": response})

    return str(cli.reply(response_body.encode("utf-8"), 200, "application/json"))
