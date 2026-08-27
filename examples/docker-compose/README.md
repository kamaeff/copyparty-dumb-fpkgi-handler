1. Put [fpkg_vault.py](https://github.com/kamaeff/fpkg-vault/releases/latest/download/fpkg_vault.py) into `handlers` folder
2. Copy `.env.example` to `.env`
3. Put your actual values into `.env`. `FILESHARE_LOCAL_PATH` is the path on your server you want to serve with copyparty/fpkg-vault
4. Set different username and password in `cfg/copyparty.conf`
5. run `docker compose up -d`
6. Access by http://<your-server-ip>:3923
