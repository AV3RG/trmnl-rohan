#!/usr/bin/env python3
"""Write the current (or last played) Spotify track to feeds/spotify.json, which the Spotify plugin polls.

Environment (from the project's .env):
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET   your app at developer.spotify.com

Usage:
  collect.py auth-url          print the link to open in a browser
  collect.py auth-listen       wait on 127.0.0.1:8888 for Spotify's redirect, then save the token
  collect.py auth-code <url>   finish with the redirected URL pasted by hand (browser on another machine)
  collect.py [--print]         fetch playback and write the feed (or just print it)
"""
import base64
import hashlib
import http.server
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-playback-state user-read-currently-playing user-read-recently-played"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token")


def env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set")
    return value


def state():
    # Derived from the client secret so auth-url and auth-listen agree without shared storage.
    return hashlib.sha256(env("SPOTIFY_CLIENT_SECRET").encode()).hexdigest()[:16]


def auth_url():
    query = urllib.parse.urlencode({
        "client_id": env("SPOTIFY_CLIENT_ID"),
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state(),
    })
    return f"https://accounts.spotify.com/authorize?{query}"


def token_request(fields):
    basic = base64.b64encode(f"{env('SPOTIFY_CLIENT_ID')}:{env('SPOTIFY_CLIENT_SECRET')}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": f"Basic {basic}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def save_refresh_token(token):
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)


def finish_auth(redirected):
    query = urllib.parse.parse_qs(urllib.parse.urlparse(redirected).query)
    if query.get("state", [""])[0] != state():
        sys.exit("state mismatch: use the link from `collect.py auth-url`")
    if "code" not in query:
        sys.exit(f"Spotify returned no code: {query.get('error', ['unknown error'])[0]}")
    tokens = token_request({"grant_type": "authorization_code", "code": query["code"][0], "redirect_uri": REDIRECT_URI})
    save_refresh_token(tokens["refresh_token"])
    print("Spotify authorised, token saved")


def auth_listen():
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith("/callback"):
                self.send_error(404)
                return
            result["url"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab.")

        def log_message(self, *args):
            pass

    with http.server.HTTPServer(("127.0.0.1", 8888), Handler) as server:
        while "url" not in result:
            server.handle_request()
    finish_auth(result["url"])


def api(path, access_token):
    req = urllib.request.Request(f"https://api.spotify.com/v1{path}", headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp) if resp.status == 200 else None


def describe(item):
    if item.get("type") == "episode":
        images = item.get("images") or item.get("show", {}).get("images") or []
        artist, album = item.get("show", {}).get("name", ""), "Podcast"
    else:
        images = item.get("album", {}).get("images") or []
        artist = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {}).get("name", "")
    minutes, seconds = divmod(item.get("duration_ms", 0) // 1000, 60)
    return {
        "track": item.get("name", ""),
        "artist": artist,
        "album": album,
        "art_url": images[0]["url"] if images else "",
        "duration": f"{minutes}:{seconds:02d}",
    }


def collect():
    try:
        with open(TOKEN_FILE) as f:
            refresh_token = f.read().strip()
    except OSError:
        sys.exit("not authorised yet: run `collect.py auth-url`")
    tokens = token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})
    if tokens.get("refresh_token"):
        save_refresh_token(tokens["refresh_token"])
    access = tokens["access_token"]

    payload = {"has_track": False, "playing": False, "device": "", "updated_at": time.strftime("%H:%M")}
    player = api("/me/player?additional_types=episode", access)
    if player and player.get("item"):
        payload.update(describe(player["item"]), has_track=True, playing=bool(player.get("is_playing")),
                       device=(player.get("device") or {}).get("name", ""))
    else:
        recent = api("/me/player/recently-played?limit=1", access)
        if recent and recent.get("items"):
            payload.update(describe(recent["items"][0]["track"]), has_track=True)
    return payload


def write_feed(name, payload):
    """Write the payload where the server's plugin polls it (feeds/<name>.json), atomically."""
    feeds = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "feeds")
    os.makedirs(feeds, exist_ok=True)
    tmp = os.path.join(feeds, f".{name}.tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(feeds, f"{name}.json"))
    print(f"wrote feeds/{name}.json")


def main():
    args = sys.argv[1:]
    if args[:1] == ["auth-url"]:
        print(auth_url())
    elif args[:1] == ["auth-listen"]:
        auth_listen()
    elif args[:1] == ["auth-code"] and len(args) == 2:
        finish_auth(args[1])
    else:
        payload = collect()
        if "--print" in args:
            print(json.dumps(payload, indent=2))
            return
        write_feed("spotify", payload)

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {e.url.split('?')[0]}: {e.read().decode()[:300]}")
