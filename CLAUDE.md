# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Docker Compose stack ("arr-stack") for automated media management on an **Unraid** server: Tailscale, SABnzbd, Prowlarr, Radarr, Sonarr, Bazarr, Seerr, Jellyfin, Homepage, and AdGuard Home (local DNS: `<service>.fritz.box` rewrites + ad blocking) active; Lidarr/Readarr, Vaultwarden, and Threadfin behind compose profiles (off by default). There is no application code, build, or test suite — the deliverables are `docker-compose.yml`, `bootstrap.sh` + `bootstrap/NN-*.sh` (idempotent API configuration), `recyclarr/recyclarr.yml`, `setup.sh`, `.env.example`, `scripts/`, and the Markdown setup guides. The stack is deployed on the Unraid host, not on this Windows machine.

## Commands

```bash
cp .env.example .env        # then edit: UNRAID_IP, TS_AUTHKEY, EWEKA_*, SCENENZBS_APIKEY, …
bash bootstrap.sh           # one-command bootstrap: dirs, network, compose up, wait healthy, API config
bash scripts/healthcheck.sh # report: containers, APIs, indexer/client tests, hardlink test
bash bootstrap/03-prowlarr.sh   # every NN-*.sh is idempotent and re-runnable on its own

docker compose --profile vaultwarden up -d vaultwarden   # optional services are behind profiles
docker compose --profile adguard up -d adguardhome       # (also: iptv, lidarr, readarr)

docker compose config -q    # validate compose file after edits
```

Images are **pinned** — updating = bump the tag in `docker-compose.yml`, `docker compose up -d`, commit. `setup.sh` (dirs + Homepage config only) remains for UI-based setups.

API bootstrap conventions: scripts source `bootstrap/lib.sh` (env loading from `.env` + `.env.runtime`, `arr_api` curl helper, `require_var`); `bootstrap/01-extract-keys.sh` writes service API keys to `.env.runtime` (gitignored, chmod 600); everything must stay idempotent (match-then-update, never blind create).

## Architecture

- **Network**: all services join `arr_net`, an **external** bridge network created by `bootstrap.sh`/`setup.sh` (declared `external: true` in compose — `docker compose up` fails if it doesn't exist). Exception: Tailscale runs in `network_mode: host` so it can reach every published port and expose the whole stack over the Tailnet without router port-forwarding.
- **Volumes**: every named volume is a bind mount (`driver_opts: type: none, o: bind`) onto `${APPDATA}/<service>`. Adding a service means adding a volume block, a directory entry in `setup.sh`'s `APPDATA_DIRS`, and usually a Homepage entry in the `services.yaml` heredoc in `setup.sh`.
- **Hardlink convention (critical)**: SABnzbd, Radarr and Sonarr all mount the whole `${DATA}` share as `/data` so downloads (`/data/downloads`) and media (`/data/media`) share one filesystem, imports use hardlinks instead of copies, and no remote path mappings are needed. Don't split these into separate mounts. Bazarr deliberately mounts only `${DATA}/media`; Jellyfin mounts it read-only.
- **`x-common` anchor** provides `restart`, PUID/PGID, and TZ. Note: an explicit `environment:` block on a service **replaces** the anchor's environment entirely (YAML merge, not deep merge), so TZ/PUID/PGID must be repeated there (see jellyfin, homepage). Seerr and Vaultwarden intentionally skip PUID/PGID (they don't use the LinuxServer user model).
- **Ports** are all `.env`-configurable with defaults chosen to avoid collisions on Unraid: SABnzbd published on 8090 (8080 is common on Unraid), AdGuard UI on 8081, AdGuard setup wizard on 3001 (Homepage owns 3000), AdGuard DNS bound to `${UNRAID_IP}:53` to avoid the host resolver on 127.0.0.1:53. Unraid defaults PUID=99/PGID=100.
- **Inter-service config** uses Docker hostnames (`http://radarr:7878`, `http://sabnzbd:8080` with the *container* port), which only resolve inside `arr_net`; browser access uses `http://<unraid-ip>:<published-port>`.

## Keeping files in sync

Service/port changes must be reflected in several places at once: `docker-compose.yml`, `.env.example`, the README tables (Services, Ports Reference) and setup instructions, and `setup.sh` (directory lists, Homepage `services.yaml` heredoc, final port printout).

The remaining `.md` files (`UNRAID_SETUP.md`, `UNRAID_UI_SETUP.md`, `DUAL_LANGUAGE_SETUP.md`, `FREUNDE_ANLEITUNG.md`, `IPTV_SETUP.md`, `VAULTWARDEN_SETUP.md`) are end-user guides written in **German** — keep additions to them in German and update them when the services they document change.
