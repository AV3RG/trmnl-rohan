<img src="assets/icon.svg" width="64" height="64" alt="">

# trmnl-rohan

Self-hosted [TRMNL](https://trmnl.com) server ([LaraPaper](https://github.com/usetrmnl/larapaper)) in Docker, shown on an always-on iPad.

| What | URL |
| --- | --- |
| Admin UI (devices, playlists, plugins) | http://192.168.1.20:4567 |
| iPad display page (HTTPS, Tailscale devices only) | https://zephyrus01.tail1b7711.ts.net/mirror/ |

## Commands

| Command | Does |
| --- | --- |
| `make up` | Start. The container restarts by itself after a crash or reboot. |
| `make restart` / `make down` | Restart / stop. |
| `make logs` | Follow server logs. |
| `make update` | Back up, then pull the version set in `.env` (`LARAPAPER_VERSION`) and restart. |
| `make backup` | Copy the sqlite database into `backups/`. |
| `make shell` | Shell inside the container (`php artisan ...`). |
| `make config-export` | Save plugins, settings, playlists and device into `config/server.json`. |
| `make config-restore` | Rebuild a server from `config/server.json`. |
| `make plugin-deploy DIR=... NAME="..."` | Upload a custom plugin from `plugins/` and write its `preview.png`. |

Settings live in `.env` (see `.env.example`). Data lives in the Docker volumes `trmnl-rohan_database` and `trmnl-rohan_generated`.

## iPad setup

1. In the admin UI, register the account, then Devices → Add New Device. Give it any MAC address and note its API key.
2. On the iPad open the display page in Safari, enter the server URL (`https://zephyrus01.tail1b7711.ts.net`) and the device API key, and turn on "Simulate physical device" so it cycles the playlist.
3. Share → Add to Home Screen to run it without browser bars.
4. Turn on Screen Wake Lock in the page's setup form. It needs HTTPS, which `tailscale serve --bg 4567` provides on this machine (the setting survives reboots); the iPad must be connected to Tailscale. `APP_URL` in `.env` must be the HTTPS address so screen images load over HTTPS too.

## Screens and plugins

Screens rotate through the device's playlist. Custom plugins are made in the admin UI under Plugins (Liquid or Blade markup plus a polling URL or webhook), or imported as TRMNL recipe zip files.

### Machine Health (custom plugin)

`plugins/machine-health/` holds the screen showing this machine's load, memory, disk, temperatures, containers, Wi-Fi and Tailscale peers.

- `collect.py` gathers the stats and posts them to the plugin's webhook (`MACHINE_HEALTH_WEBHOOK` in `.env`). `collect.py --print` shows the payload without sending.
- A systemd user timer runs it every 5 minutes: `systemctl --user status trmnl-machine-health.timer`. Copies of the unit files are in `systemd/`.
- `template.liquid` is the screen layout. After editing it, run `make plugin-deploy DIR=machine-health NAME="Machine Health"`, which uploads it and writes `preview.png`.

### Other custom plugins

- `plugins/spotify/`: now playing. `collect.py` runs every minute from a systemd user timer and needs `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_WEBHOOK` in `.env`. Sign in once with `collect.py auth-url`, then `collect.py auth-code <redirected url>`.
- `plugins/github-commit-graph/`: a port of TRMNL's hosted GitHub Commit Graph plugin. It polls GitHub itself; `plugin.json` holds its data source and settings fields, and the token is entered in the admin UI.

## Configuration in git

`config/server.json` records every installed plugin (with where it was installed from), its non-secret settings, the playlists and the device. Run `make config-export` after changing things in the admin UI, then commit the file.

Tokens, the device API key and `.env` are never exported. To rebuild on a fresh machine:

1. `make up`, then register the account in the admin UI.
2. `make config-restore`. It prints the webhook URLs of the custom plugins and the list of plugins that need a token.
3. Put the new webhook URLs in `.env`, re-enter the tokens under Plugins, and enter the new device API key on the iPad.

A plugin installed through the admin UI has no recorded source until you add one to its entry in `config/server.json`; `make config-export` warns about these.
