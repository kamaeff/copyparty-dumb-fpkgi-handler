# copyparty-dumb-fpkgi-handler
Copyparty on404 handler enabling your copyparty instance to work as an FPKGi server for playstation homebrew packages.

### Maintenance notice

Starting from 2026-08-18 the repo is under maintenance. Big update is coming, but files in the master branch may be broken during that stage.
If you need a working version, just grab it from the changelog below.

### Changelog

- [2026-05-03](https://github.com/kamaeff/copyparty-dumb-fpkgi-handler/tree/652c295d46c416710bc240bf7664bacb74e19f74):
    - Now it servers PKG's metadata: Title IDs, Title Names, Regions, Categories, Versions, Required FW versions and Cover Images
    - Now it also respects copyparty's VFS and permissions.
    - Added multiple endpoints to serve packages grouped by category (Games, DLC, Updates, PS2 Games etc.)
    - Added simple in-memory TTL-cache for packages endpoints to skip rescanning on sequential requests for different categories
- [Initial version 2026-04-17](https://github.com/kamaeff/copyparty-dumb-fpkgi-handler/tree/7c3bd1339f380d36a0c6272ffba1171db3a03450):
    - > It's simple and dumb. It does not read package SFO metadata. It does not validate package files. It does not cache anything. 
    - > It just adds FPKGi-style JSON generation to your working copyparty instance. And it populates new downloaded packages to FPKGi as soon as they are downloaded.
    - Has single endpoint with all packages, serves PKG files, scans folders recursively, ignores copyparty's VFS, no metadata, no cover images, no caching.

### Background and motivation
- I download PS4 packages from the internets directly to my NAS
- I use copyparty to access files on the NAS and I don't want to introduce another file server application
- I want to use FPKGi to utilize its backgound download feature
- I want packages downloaded from the internets to be available in FPKGi immediately without manual JSON creation/editing
- I dont' care for metadata correctness. File name is enough to distinguish different downlaoded packages.
- I don't have free time to understand PKG SFO metadata extraction, write and debug a reliable solution for that

So I made a simple plug-in script that can serve my downloaded packages for FPKGi directly from copyparty.
Later on I've added metadata support, but it's still a single dumb Python script.


### Example

[Here](https://github.com/kamaeff/home-server/tree/edd198b06d2546a8cff2109c656d587f769438d1/copyparty) you can see a docker-compose example from my actual home server. 

###### copyparty config

Let's see an example with this copyparty config:

`copyparty.conf`
```yaml
[accounts]
  AzureDiamond:hunter2

# your existing copyparty filesystem
[/home]
  /home/AzureDiamond
  accs:
    A: AzureDiamond

# your new special copyparty filesystem for accessing homebrew FPKGs
[/homebrew]
  /home/AzureDiamond/Downloads
  accs:
    g: *
  flags:
    on404: /home/AzureDiamond/scripts/fpkgi.py
```

`g: *` permission in `accs:` means that anyone can get files by a direct link, but cannot list file directories. `g` is the minimal required access level to use with copyparty-dumb-fpkgi-handler. Any of `r`, `g`, `u`, `h`, `a`, `A` would work.

Here we saved `fpkgi.py` into `/home/AzureDiamond/scripts` folder and use it as `on404` handler for `/homebrew` copyparty mount.

Homebrew PS4 packages are downloaded into `/home/AzureDiamond/Downloads`.
The `__FPKGi.json` file should not exist in the Downloads folder.

###### FPKGi config – single endpoint
When you access `http://yourserver.com/homebrew/__FPKGi.json`, copyparty calls `fpkgi.py` to handle a 404 error. 
`fpkgi.py` scans  `/home/AzureDiamond/Downloads` folder recursively for any `.pkg` files. (Note: **actually** it scans copyparty's `/homebrew` mount with respect to copyparty's VFS and access settings).
It generates an FPKGi-compatible JSON and returns it. 

Now it's time to update our FPKGi `CONTENT_URLS` setting on PS4 system:
`/user/data/FPKGi/config.json`
```json
    "CONTENT_URLS": {
      "PS1": null, "PS2": null, "PSP": null, "PS5": null, "games": null, "emulators": null,
      "apps": null, "updates": null, "DLC": null, "demos": null, "themes": null,

      "homebrew": "http://yourserver.com/homebrew/__FPKGi.json",
    }
```

Don't forget to enable "Populate via Web" setting in FPKGi.

Then when FPKGi app is started it will show all `.pkg` files from `/home/AzureDiamond/Downloads` folder and will be able to download them. 

Note that with provided configuration such packages will appear with `homebrew` content type in FPKGi app. If you want you can set up different copyparty mounts for different content types and manually move pkg files around. 

###### FPKGi config – endpoints by category
It is also possible to set up different `CONTENT_URLS` to filter served packages by their category/content type. Content type is determined by package's metadata.

Currently supported content types are:
- `DLC`
- `games`
- `apps`
- `PS2`
- `updates`
- `homebrew` (apps only assigned this category if the script couldn't determine their actual category from metadata)

All these categories are served with urls like `/__FPKGi_\<category name\>.json`.

So the `CONTENT_URLS` config section in `/user/data/FPKGi/config.json` on your PS4 should look like this:
```json
    "CONTENT_URLS": {
      "PS1": null,
      "PS2": "http://yourserver.com/homebrew/__FPKGi_PS2.json",
      "PSP": null,
      "PS5": null,
      "games": "http://yourserver.com/homebrew/__FPKGi_games.json",
      "apps": "http://yourserver.com/homebrew/__FPKGi_apps.json",
      "updates": "http://yourserver.com/homebrew/__FPKGi_updates.json",
      "DLC": "http://yourserver.com/homebrew/__FPKGi_DLC.json",
      "demos": null,
      "homebrew": "http://yourserver.com/homebrew/__FPKGi_homebrew.json",
      "emulators": null,
      "themes": null
    }
```

### Authentication

If you need to serve from password-protected mount, there are two options:
- use basic auth: `"homebrew": "http://AzureDiamond:hunter2@yourserver.com/homebrew/__FPKGi.json",` (Note that `no-bauth` flag should be unset in `copyparty.conf`)
- set up [ipauth](https://github.com/9001/copyparty/blob/a997455b5a3d937f53ad40f431534a0e3865e9f7/docs/chungus.conf#L445) for requests coming from your PS4


### Acknowledgements
- [copyparty](https://copyparty.eu) – file server I love; created by @9001
- [FPKGi](https://github.com/ItsJokerZz/FPKGi) – PS4 package installer, clone of PKGi homebrew; created by @ItsJokerZz
