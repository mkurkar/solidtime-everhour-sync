# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-14

### Added
- Phase 1 structure sync: Everhour → Solidtime (projects + tasks under one Client)
- Phase 2 time-entry sync: Solidtime → Everhour with deduplication
- Local JSON-based mapping store with per-project incremental saves
- APScheduler-based daemon with CLI `--once` mode
- Dockerfile + docker-compose.yml for production deployment
- Per-request delay + retry logic for flakey self-hosted instances
- Per-task error isolation so a single bad task doesn't abort the run
