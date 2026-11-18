<img src="assets/icon.svg" width="64" height="64" alt="">

# trmnl-rohan

Self-hosted [TRMNL](https://trmnl.com) server ([LaraPaper](https://github.com/usetrmnl/larapaper)) in Docker, shown on an always-on iPad.

| What | URL |
| --- | --- |
| Admin UI (devices, playlists, plugins) | http://192.168.1.20:4567 |
| iPad display page | http://192.168.1.20:4567/mirror/ |

## Commands

| Command | Does |
| --- | --- |
| `make up` | Start. The container restarts by itself after a crash or reboot. |
| `make restart` / `make down` | Restart / stop. |
| `make logs` | Follow server logs. |
| `make update` | Back up, then pull the version set in `.env` (`LARAPAPER_VERSION`) and restart. |
| `make backup` | Copy the sqlite database into `backups/`. |
| `make shell` | Shell inside the container (`php artisan ...`). |

Settings live in `.env` (see `.env.example`). Data lives in the Docker volumes `trmnl-rohan_database` and `trmnl-rohan_generated`.

## iPad setup

1. In the admin UI, register the account, then Devices → Add New Device. Give it any MAC address and note its API key.
2. On the iPad open the display page in Safari, enter the server URL (`http://192.168.1.20:4567`) and the device API key, and turn on "Simulate physical device" so it cycles the playlist.
3. Share → Add to Home Screen to run it without browser bars.
4. Set Settings → Display & Brightness → Auto-Lock to Never. The page's own keep-awake toggle needs HTTPS, which this setup does not have.

## Screens and plugins

Screens rotate through the device's playlist. Custom plugins are made in the admin UI under Plugins (Liquid or Blade markup plus a polling URL or webhook), or imported as TRMNL recipe zip files.

### Machine Health (custom plugin)

`plugins/machine-health/` holds the screen showing this machine's load, memory, disk, temperatures, containers, Wi-Fi and Tailscale peers.

- `collect.py` gathers the stats and posts them to the plugin's webhook (`MACHINE_HEALTH_WEBHOOK` in `.env`). `collect.py --print` shows the payload without sending.
- A systemd user timer runs it every 5 minutes: `systemctl --user status trmnl-machine-health.timer`. Copies of the unit files are in `systemd/`.
- `template.liquid` is the screen layout. After editing it, run `make plugin-deploy DIR=machine-health NAME="Machine Health"`, which uploads it and writes `preview.png`.
