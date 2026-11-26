# OMEGA DECK

Personal operations deck — gateway dashboard, blue-team sentry grid,
collaborative whiteboard, video render farm, and learning academy.

## Layout

| Folder | Meaning |
|---|---|
| `gateway.py` | Ops gateway on :8088 — app launcher, marshal-key auth, sentry hooks |
| `sentry.py` | Blue-team detection grid — 9 regex rules, `detections.jsonl` alerts |
| `updater.py` / `corps.py` / `marshal_codec.py` | Fleet updater, corps registry, marshal crypto |
| `ops-board/` | Live whiteboard service (:8901) — type shapes, draw live |
| `video-pipeline/` | Render farm (:8898) — scene-forge compatible, image vault, stock fetcher, video-DNA |
| `academy/` | Learning library — security, engineering, knowledge maps |
| `agents/` `ainet/` `experience/` `world/` | Agent registry, AI network proposals, experience logs, world state |

Secrets (`*.key`), media, logs, and runtime state are gitignored.
