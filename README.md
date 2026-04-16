# copyparty-dumb-fpgki-handler
Copyparty on404 handler enabling your copyparty instance to work as an FPKGi server for playstation homebrew packages.

It's simple and dumb. It does not read package SFO metadata. It does not validate package files. It does not cache anything.  
It just adds FPKGi-style JSON generation to your working copyparty instance. And it populates new downloaded packages to FPKGi as soon as they are downloaded.

### Background and motivation
- I download PS4 packages from the internets directly to my NAS
- I use copyparty to access files on the NAS and I don't want to introduce another file server application
- I want to use FPKGi to utilize its backgound download feature
- I want packages downloaded from the internets to be available in FPKGi immediately without manual JSON creation/editing
- I dont' care for metadata correctness. File name is enough to distinguish different downlaoded packages.
- I don't have free time to understand PKG SFO metadata extraction, write and debug a reliable solution for that

So I made a simple plug-in script that can serve my downloaded packages for FPKGi directly from copyparty.


### Example
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

Here we saved `fpkgi.py` into `/home/AzureDiamond/scripts` folder and use it as `on404` handler for `/homebrew` copyparty mount.  
Homebrew PS4 packages are downloaded into `/home/AzureDiamond/Downloads`.
The `__FPKGi.json` file should not exist in the Downloads folder.

When you access `http://yourserver.com/homebrew/__FPKGi.json`, copyparty calls `fpkgi.py` to handle a 404 error. 
`fpkgi.py` scans `/home/AzureDiamond/Downloads` folder recursively for any `.pkg` files.
It generates an FPKGi-compatible JSON and returns it. 
JSON is never saved on disk or cached. Each time you open `__FPKGi.json` it is recreated in memory the same way.

Now it's time to update our FPKGi `CONTENT_URLS` setting on PS4 system:
`/user/data/FPKGi/config.json`
```json
    "CONTENT_URLS": {
      "PS1": null, "PS2": null, "PSP": null, "PS5": null, "games": null, "emulators": null,
      "apps": null, "updates": null, "DLC": null, "demos": null, "themes": null,

      "homebrew": "http://yourserver.com/fpkgi/__FPKGi.json",
    }
```

Don't forget to enable "Populate via Web" setting in FPKGi.

Then when FPKGi app is started it will show all `.pkg` files from `/home/AzureDiamond/Downloads` folder and will be able to download them. 

Note that with provided configuration such packages will appear with `homebrew` content type in FPKGi app. If you want you can set up different copyparty mounts for different content types and manually move pkg files around. 

If you need to serve from password-protected mount, there are two options:
- use basic auth: `"homebrew": "http://AzureDiamond:hunter2@yourserver.com/fpkgi/__FPKGi.json",` (Note that `no-bauth` flag should be unset in `copyparty.conf`)
- set up [ipauth](https://github.com/9001/copyparty/blob/a997455b5a3d937f53ad40f431534a0e3865e9f7/docs/chungus.conf#L445) for requests coming from your PS4


### Downsides
- file names used instead of correct Title Names
- only `CUSA` TitleIds parsed from file names. If file name doesn't contain `CUSA00000` id then it defaults to `UNKNOWN`
- no package version, required firmware, release date, cover image provided

### Acknowledgements
- [copyparty](https://copyparty.eu) – file server I love; created by @9001
- [FPKGi](https://github.com/ItsJokerZz/FPKGi) – PS4 package installer, clone of PKGi homebrew; created by @ItsJokerZz
