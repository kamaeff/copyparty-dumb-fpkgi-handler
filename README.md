# fpkg-vault
[![justforfunnoreally.dev badge](https://img.shields.io/badge/justforfunnoreally-dev-9ff)](https://justforfunnoreally.dev)

A set of plugins for [copyparty](https://github.com/9001/copyparty) for managing and installing playstation4 homebrew apps and games (`.pkg`) and payloads(`.bin`, `.elf`).

Watch a [showcase video on youtube](https://youtu.be/5eBbjtoWfsk) or play around with [demo server](https://files.kamaeff.com/public/fpkg-demo/).

**This plugin requires GoldHEN on your console running Payloader server**  
To enable payloader server:
- go to GoldHEN menu > Server Settings
- tick `Enable Payloader Server`

To try it yourself and play around:
- install python
- install mutagen (optional, enables metadata tags) and pillow (optional, enables fpkg thumbnails in copyparty webview)
- grab latest `copyparty-sfx.py` from [copyparty releases page](https://github.com/9001/copyparty/releases/latest)
- grab latest `fpkg_vault.py` from [fpkg-vault releases page](https://github.com/kamaeff/fpkg-vault/releases/latest)
- drop them into folder with some fpkg files
- run `FPKGV_PS4_IP=your-ps4-lan-ip FPKGV_CP_HOST=http://your-computer-lan-ip:3923 python3 ./fpkg_vault.py demo run`

Example for Debian Linux:
```bash
sudo apt-get update && sudo apt-get upgrade
sudo apt-get install python3 python3-mutagen python3-pil

cd /mnt/fpkg-collection/

wget https://github.com/9001/copyparty/releases/latest/download/copyparty-sfx.py
wget https://github.com/kamaeff/fpkg-vault/releases/latest/download/fpkg_vault.py

FPKGV_PS4_IP=192.168.1.125 FPKGV_CP_HOST=http://192.168.1.100:3923 python3 ./fpkg_vault.py demo run
```

Then open http://127.0.0.1:3923 in the browser.

To learn how to run it in docker environment, check out [examples](./examples).

And please refer to copyparty [README](https://github.com/9001/copyparty/blob/hovudstraum/README.md) and [helptext](https://copyparty.eu/cli)!

### Features
fpkg-vault provides:
- custom thumbnail-extractor for `.pkg` files ([copyparty option](https://copyparty.eu/cli/#g-th-extract)) to show fpkg thumbnails in copyparty web ui
- custom tags extractor for `.pkg` files ([copyparty option](https://copyparty.eu/cli/#g-mtp)) to show fpkg metadata in copyparty web ui
- on404 and on403 handlers ([copyparty options](https://copyparty.eu/cli/#g-on404)) doing most of the server-side job:
  - sending packages and payloads directly from server to console
  - FPKGi-compatible server to install your apps and games right in [FPKGi](https://github.com/ItsJokerZz/FPKGi) app on your console
- custom javascript and css to add install buttons and toasts in copyparty web ui ([copyparty options](https://copyparty.eu/cli/#g-css-browser))
- all of it in a single python file!

### Installation

For complete docker compose setup look into [examples](./examples).

First of all, download latest `fpkg_vault.py` from [fpkg-vault releases page](https://github.com/kamaeff/fpkg-vault/releases/latest).

Basically you need to run copyparty with some options set either as cli arguments or in config file. Here we use a config file `copyparty.conf` assuming that `fpkg_vault.py`'s location is `~/partyhandlers/fpkg_vault.py` and fpkg files are located somewhere in `/mnt/big-drive`.

```yaml
[global]
# general options
  name: fpkg-vault
  e2dsa             # enable file indexing and filesystem scanning
  e2ts              # enable multimedia indexing
  re-maxage: 3600   # rescan fs for changes every hour

# fpkg vault related options
  # handle 404 errors with fpkg-vault
  on404: ~/partyhandlers/fpkg_vault.py
  # handle 403 errors with fpkg-vault
  on403: ~/partyhandlers/fpkg_vault.py
  # extract fpkg tags using fpkg-vault
  mtp: type,category,title,title_id,content_id,app_ver,version,system_ver=ad,epkg,c1,f,~/partyhandlers/fpkg_vault.py
  # save extracted tags and show them in ui
  mte: +type,category,title,title_id,content_id,app_ver,version,system_ver
  # extract thumbnail from .pkg files using fpkg-vault
  th-extract: pkg=~/partyhandlers/fpkg_vault.py
  # custom javascript (served by previously set on404 handler)
  js-browser: /__fpkgv/script.js
  # custom css (served by previously set on404 handler)
  css-browser: /__fpkgv/style.css

[accounts]
  mycoolusername:unguessablepassword

[/]                 # this url in browser
  /mnt/big-drive    # is mapped to this folder on server
  accs:             # access permissions
    A: mycoolusername   # A is a shorthand for 'all permissions', read copyparty readme on permissions to learn more
```

Run copyparty with this config. 
Note that there are optional dependencies:
- for thumbnails your need Pillow and/or pyvips and/or ffmpeg
- for metadata tags you need either mutagen or ffprobe

fpkg and paylod sender and FPKGi server have no external dependencies.
To ensure you have all the necessary dependencies and to run it as background service it's recommended to use one of [copyparty docker images](https://github.com/9001/copyparty/tree/hovudstraum/scripts/docker#editions).



### Configuration

While copyparty can be configured with cli args and config files, fpkg vault is only configured via environment variables.

#### `FPKGV_PS4_IP`

**Required**: yes  
**Default value**: empty

Comma-separated list of LAN IP addresses of your PS4 consoles.
The simplest case is just a single IP address of your only console.
The first address from the list is used by sender to send payloads and packages to.
All the other IP addresses get privileged access to FPKGi JSON files.
Privileged access means:
- console can get any PKG file or PKG cover image on server by direct url
- when requesting FPKGi json files, the console gets list of all PKG files on server regardless of permissions set in copyparty config


To limit what packages are available to the console in FPKGi you can authenticate it
with copyparty options --ipu and optionally --ipr, eg:
--ipu 192.168.1.125/32=ps4_living_room
--ipr 192.168.1.125/32=ps4_living_room
where '192.168.1.125' is the console's IP address
and 'ps4_living_room' is the copyparty username to force authentication with;
after this you can set 'ps4_living_room' user permissions in copyparty config:
https://github.com/9001/copyparty/tree/hovudstraum#accounts-and-volumes

The privilege to get any PKG file or PKG cover image on server by direct url is
required to allow different users to send packages to PS4 with zero permissions setup
If you want the PS4 to fully obey copyparty's permissions settings, in addition to
previously mentioned --ipu, set the environment variable FPKGV_RESTRICT_PS4_ACCESS=true

#### `FPKGV_RESTRICT_PS4_ACCESS`

**Required**: no  
**Default value**: empty

Set to `true` to remove `FPKGV_PS4_IP` priveleged access and make it obey copyparty permission configuration.

#### `FPKGV_SEND_USERS`

**Required**: no  
**Default value**: `*`

Who can send payloads and packages to the console.  
Comma-separated list of copyparty usernames and group names allowed to send.  
Group names start with `@`.  
Prefix username or groupname with `-` to explicitly deny them send access.  
There is a special group in copyparty, `@acct`, which includes all authenticated users.  
Use `*` to allow anyone to send packages.
Examples:
- `FPKGV_SEND_USERS='*'` – anyone allowed to send packages (default)
- `FPKGV_SEND_USERS='@acct'` – allow any authenticated users to send packages
- `FPKGV_SEND_USERS='miles,tony'` – only allow miles and tony to send packages
- `FPKGV_SEND_USERS='@acct,-alex'` – allow any authenticated user to send packages, except alex
- `FPKGV_SEND_USERS='@home,-@kids'` – allow users from group 'home' to send packages, but exclude users from group 'kids'
- `FPKGV_SEND_USERS='@acct,-@adults'` – kids revenge! allow any authenticated user to send packages, but exclude users from group 'adults'

Having 'read' access to a package file is the baseline requirement to send it.  
You can make that requirement stricter by adding '#' followed by any combination of letters 'wmda' to require additional access levels:
- w – also require 'write' access to the file to be able to send it
- m – also require 'move' permission
- d – also require 'delete' permission
- a – also require 'admin' permission

examples:
- `FPKGV_SEND_USERS='#wmd,*'` – anyone can send packages they have 'read' (baseline), 'write', 'move' and 'delete' access to at the same time
- `FPKGV_SEND_USERS='#wmd,#wa,*'` – require either 'read,write,move,delete' or 'read,write,admin' permission level
- `FPKGV_SEND_USERS='#wa,@acct,-jane'` – any authenticated user (except jane) can send a package if they have at the same time 'read' (baseline), 'write' and 'admin' access to it

note that 'deny' rules always take precedence, so if you have `@home,-@kids,alex` and alex is in group 'kids', then alex will not be able to send packages because he is excluded by '-@kids' rule

#### `FPKGV_CP_HOST`

**Required**: no
**Default value**: empty

LAN address of your copyparty instance.  
When you 'send PKG' to the playstation, you actually send a tiny payload.  
That payload tells the PS4 where to grab an actual PKG file from.  
If you specify the `FPKGV_CP_HOST` then the payload will contain links to that host.  
Otherwise the host copyparty is accessed by (e.g. address in your browser address line) will be used.

useful in cases:
- you access copyparty externally (e.g. https://party.mycool.name served via cloudflare tunnels)  
  and asking the PS4 to download packages over the internet is inefficient;  
  in that case you can set FPKGV_CP_HOST='http://192.168.1.227:3923'  
  and PS4 will go to local address http://192.168.1.227:3923 instead of external https://party.mycool.name  
- you run copyparty on your main computer and access it with 'http://127.0.0.1:3923'
  in that case sending payloads with that host will lead to that PS4 can't download anything
  so you better set `FPKGV_CP_HOST` to the copyparty's LAN address

if you only access copyparty by LAN address then FPKGV_CP_HOST is optional

### FPKGi server

fpkg vault serves json files consumable by ItsJokerZz's [FPKGi app](https://github.com/ItsJokerZz/FPKGi).  
It recursively scans each volume and its subvolumes and creates special endpoints for each volume:
- `<volume url>/__fpkgv/all.json` contains all found PKG files
- `<volume url>/__fpkgv/PS2.json` – PKG files with PS2-like `TITLE_ID`s
- `<volume url>/__fpkgv/games.json` – PKG files with metadata saying its a game package
- `<volume url>/__fpkgv/apps.json` – PKG files with metadata saying its an app package
- `<volume url>/__fpkgv/updates.json` – PKG files with metadata saying its an update package
- `<volume url>/__fpkgv/DLC.json` – PKG files with metadata saying its a DLC package
- `<volume url>/__fpkgv/homebrew.json` – used if no other category could be determined by package metadata

in the most basic case you just run a single `/` volume
and if your copyparty instance address is `http://192.168.1.227:3923`  
then these json endpoints are accessible as `http://192.168.1.227:3923/__fpkgv/all.json` and so on.  

In this case `CONTENT_URLS` section of your FPKGi config may look like this:
```json
    "CONTENT_URLS": {
      "PS1": null,
      "PS2": "http://192.168.1.227:3923/__fpkgv/PS2.json",
      "PSP": null,
      "PS5": null,
      "games": "http://192.168.1.227:3923/__fpkgv/games.json",
      "apps": "http://192.168.1.227:3923/__fpkgv/apps.json",
      "updates": "http://192.168.1.227:3923/__fpkgv/updates.json",
      "DLC": "http://192.168.1.227:3923/__fpkgv/DLC.json",
      "demos": null,
      "homebrew": "http://192.168.1.227:3923/__fpkgv/homebrew.json",
      "emulators": null,
      "themes": null
    }
```


if you want to manually manage these categories, you can create different copyparty
volumes for each of them. And use each volume's `all.json` endpoint in FPKGi config.  
For example, volumes section in copyparty config:
```yaml
[/]
  /mnt/big-drive
  accs:
    A: mycoolusername
[/games]
  /mnt/big-drive/games
  accs:
    A: mycoolusername
[/homebrew]
  /mnt/big-drive/homebrew
  accs:
    A: mycoolusername
[/emulators]
  /mnt/big-drive/emulators
  accs:
    A: mycoolusername
```

and corresponding `CONTENT_URLS` section of FPKGi config:
```json
    "CONTENT_URLS": {
      "PS1": null,
      "PS2": null,
      "PSP": null,
      "PS5": null,
      "games": "http://192.168.1.227:3923/games/__fpkgv/all.json",
      "apps": null,
      "updates": null,
      "DLC": null,
      "demos": null,
      "homebrew": "http://192.168.1.227:3923/homebrew/__fpkgv/all.json",
      "emulators": "http://192.168.1.227:3923/emulators/__fpkgv/all.json",
      "themes": null
    }
```

or if you don't care at all:
```yaml
[/]
  /mnt/big-drive
  accs:
    A: mycoolusername
```
```json
    "CONTENT_URLS": {
      "PS1": null,
      "PS2": null,
      "PSP": null,
      "PS5": null,
      "games": "http://192.168.1.227:3923/__fpkgv/all.json",
      "apps": null,
      "updates": null,
      "DLC": null,
      "demos": null,
      "homebrew": null,
      "emulators": null,
      "themes": null
    }
```

### Build from source
Build requirements are:
- x86_64 machine
- python3
- python3-rjsmin(optional)
- gcc
- yasm
- make

to build, run:
```bash
make
```


### Changelog
- [2026-08-27](https://github.com/kamaeff/fpkg-vault/tree/7da3b52deb4353da10cb1bc4ed44847c7fdda400)
    - renamed project: copyparty-dumb-fpkgi-handler -> fpkg-vault
    - changed license: UNLICENSE -> AGPLv3
    - added thumbnail extractor
    - added tagging plugin
    - added fpkg and payload sender
    - first github release
- [2026-05-03](https://github.com/kamaeff/copyparty-dumb-fpkgi-handler/tree/652c295d46c416710bc240bf7664bacb74e19f74):
    - Now it servers PKG's metadata: Title IDs, Title Names, Regions, Categories, Versions, Required FW versions and Cover Images
    - Now it also respects copyparty's VFS and permissions.
    - Added multiple endpoints to serve packages grouped by category (Games, DLC, Updates, PS2 Games etc.)
    - Added simple in-memory TTL-cache for packages endpoints to skip rescanning on sequential requests for different categories
- [Initial version 2026-04-17](https://github.com/kamaeff/copyparty-dumb-fpkgi-handler/tree/7c3bd1339f380d36a0c6272ffba1171db3a03450):
    - > It's simple and dumb. It does not read package SFO metadata. It does not validate package files. It does not cache anything. 
    - > It just adds FPKGi-style JSON generation to your working copyparty instance. And it populates new downloaded packages to FPKGi as soon as they are downloaded.
    - Has single endpoint with all packages, serves PKG files, scans folders recursively, ignores copyparty's VFS, no metadata, no cover images, no caching.
