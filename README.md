# solidtime-everhour-sync

Two-way sync between a **self-hosted Solidtime** instance and **Everhour** (which itself bridges to Linear).

```
   Linear  ◄──────►  Everhour  ◄──────►  Solidtime (self-hosted)
   (source of         (bridge /           (your tracker,
   structure)        Linear proxy)        source of truth for time)
```

Structured work (projects, tasks) flows **Everhour → Solidtime**. Time entries flow **Solidtime → Everhour**, so hours logged in Solidtime show up against the right Linear issues without you ever opening Everhour.

## Why this exists

Linear's native time tracking is limited. Everhour plugs into Linear nicely, but the Everhour UI is awkward for daily use — most teams prefer a more capable time tracker like Solidtime and only need Everhour as a bridge so Linear sees the hours.

This project lets you keep using Solidtime as your everyday time tracker while keeping Linear's reports populated automatically. It also stays useful even after Linear ships better time tracking: Solidtime's self-hosted nature, project hierarchy, and reporting are the real reasons teams pick it.

## Features

- **Structure sync** — pulls every project and task from Everhour (Linear-linked or not) and mirrors them under one Solidtime Client, preserving Linear issue IDs in task names (`[TEAM-123] Task name`)
- **Time-entry sync** — pushes new Solidtime time entries to Everhour against the matching Linear task, with deduplication via a local mapping store
- **Incremental saves** — each project is committed as it syncs, so a long initial sync can be resumed by simply re-running
- **Resilient network handling** — small per-request delay, automatic retries on connection drops, and per-task/per-project error isolation so one bad item never aborts the run
- **Two deployment modes** — run once from the CLI, or run as a daemon on a cron-like interval
- **One-config-file setup** — no YAML, no `.env`, no database; everything lives in a single `config.json`

## Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌──────────┐
│   Linear    │ ◄─────► │     Everhour     │ ◄─────► │ Solidtime│
│ (projects,  │ built-in│   (bridge API)   │  custom │(self-host│
│    tasks)   │         │                  │  sync   │  ed)     │
└─────────────┘         └──────────────────┘         └──────────┘
        ▲                       ▲                       ▲
        │ hours visible here    │                       │ hours logged here
        │   via Everhour ◄─────┴───── Phase 2 ◄─────────┘
```

### Phase 1 — Structure (Everhour → Solidtime)

1. Ensure a single Client (configured via `sync.client_name`) exists in Solidtime
2. Fetch every project from Everhour
3. For each project, find-or-create a matching Solidtime project under that Client
4. Fetch every task for the project from Everhour
5. For each task, find-or-create a matching Solidtime task whose name is prefixed with the Linear issue UUID (`[li:UUID] <Task Name>`)
6. Persist a mapping `everhour_id ↔ solidtime_id` after each project, so a restart picks up cleanly

### Phase 2 — Time entries (Solidtime → Everhour)

1. Fetch Solidtime time entries modified in the last N days
2. For each entry without a mapping, look up its Solidtime task, then the matching Everhour task ID
3. POST the duration to Everhour against that task ID
4. Persist the new mapping so the entry is never pushed twice

The Solidtime task ID → Everhour task ID mapping is what keeps everything linked. Phase 1 is the only place those links are created.

## Installation

### Option A — Docker (recommended for servers)

```bash
git clone https://github.com/mkurkar/solidtime-everhour-sync.git
cd solidtime-everhour-sync
cp config.json.example config.json
# edit config.json with your Solidtime + Everhour credentials
docker compose up -d
```

Logs:

```bash
docker compose logs -f sync
```

### Option B — Local Python

```bash
git clone https://github.com/mkurkar/solidtime-everhour-sync.git
cd solidtime-everhour-sync
python -m venv venv
source venv/bin/activate
pip install -e .

cp config.json.example config.json
# edit config.json
```

## Configuration

A single `config.json` file controls everything:

```json
{
  "solidtime": {
    "base_url": "https://solidtime.your-domain.com",
    "api_token": "your-solidtime-api-token",
    "organization_id": "your-organization-uuid"
  },
  "everhour": {
    "api_token": "your-everhour-api-key"
  },
  "sync": {
    "client_name": "Your Company Name",
    "schedule_minutes": 15,
    "days_back": 7
  },
  "mappings": {
    "projects": {},
    "tasks": {},
    "time_entries": {}
  }
}
```

| Field | Description |
|---|---|
| `solidtime.base_url` | Your self-hosted Solidtime URL |
| `solidtime.api_token` | API token from your Solidtime profile |
| `solidtime.organization_id` | Your organization UUID |
| `everhour.api_token` | API key from your Everhour profile |
| `sync.client_name` | Name of the single Solidtime Client that wraps all Linear projects |
| `sync.schedule_minutes` | Daemon interval (ignored when using `--once`) |
| `sync.days_back` | How far back to look for new Solidtime time entries |
| `mappings.*` | Persisted across runs — do not edit manually |

### Getting API credentials

**Solidtime API token**
1. Sign in to your Solidtime instance
2. Profile → Settings → API tokens → Create token
3. Copy the UUID of your organization from the URL when viewing it (`/organizations/<uuid>/...`)

**Everhour API key**
1. Sign in at <https://app.everhour.com>
2. Profile → bottom of the page → API key
3. Make sure you've connected Everhour to your Linear workspace first

## Usage

### Run a single sync (initial setup or one-shot)

```bash
python -m solidtime_everhour --once
```

The first run creates all projects and tasks in Solidtime. With a few hundred Linear tasks this can take several minutes; subsequent runs are fast because they only sync what's new.

### Skip structure sync (time entries only)

Once your Solidtime projects/tasks are already in shape and you only want to push new time entries to Everhour/Linear, skip Phase 1 with either of these:

```bash
# Per-invocation flag
python -m solidtime_everhour --once --skip-structure

# Or set it permanently in config.json
# (then run normally as the daemon)
```

```json
{
  "sync": {
    "skip_structure": true
  }
}
```

The CLI flag overrides `config.json` only for that one run; the config value sticks until you flip it back.

### Run as a daemon

```bash
python -m solidtime_everhour
```

This runs the initial sync immediately, then keeps syncing every `schedule_minutes` until you stop it.

### Docker daemon

```bash
docker compose up -d
docker compose logs -f sync
```

To change the schedule, edit the `schedule_minutes` value in `config.json` and restart the container.

## Limitations and trade-offs

- **Solidtime is the source of truth for hours.** Deleting a Solidtime entry does *not* delete the Everhour/Linear one — you'll have to clean those up manually if needed.
- **Structure is one-way.** Renaming or deleting a project/task in Solidtime won't propagate back to Everhour/Linear. Make structural changes in Linear.
- **Existing time entries on unsynced tasks are skipped.** Any hours you logged in Solidtime *before* setting up this sync, on tasks that weren't created by Phase 1, will not be pushed. Log new hours on synced tasks (those whose names start with `[li:UUID]`).
- **Linear tasks appear with UUIDs in Solidtime, not human-readable IDs like `TEAM-123`.** Everhour's API exposes tasks by their internal UUID prefixed with `li:`. The script preserves those exactly so the link to Linear stays intact.
- **Rate-limited friendly, but not blazing.** A 0.3s delay between Solidtime requests avoids overloading a self-hosted instance. For very large Linear workspaces the initial sync can take 10+ minutes.

## Contributing

Issues and PRs welcome. Please don't commit any real `config.json`, Solidtime tokens, or Everhour API keys — `.gitignore` excludes them, but double-check your diff before pushing.

## License

MIT — see [`LICENSE`](LICENSE).
