"""Configuration loader for solidtime-everhour-sync."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SolidtimeConfig:
    base_url: str
    api_token: str
    organization_id: str


@dataclass
class EverhourConfig:
    api_token: str
    base_url: str = "https://api.everhour.com"


@dataclass
class SyncConfig:
    client_name: str
    schedule_minutes: int = 15
    days_back: int = 7
    skip_structure: bool = False  # set true to only push time entries


@dataclass
class Mappings:
    """Persistent mappings between Everhour and Solidtime IDs."""

    projects: dict[str, str] = field(default_factory=dict)
    tasks: dict[str, str] = field(default_factory=dict)
    time_entries: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    solidtime: SolidtimeConfig
    everhour: EverhourConfig
    sync: SyncConfig
    mappings: Mappings

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        if path is None:
            path = os.environ.get("CONFIG_PATH", "config.json")

        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}. "
                "Copy config.json.example to config.json and fill in your credentials."
            )

        with open(config_path) as f:
            data = json.load(f)

        return cls(
            solidtime=SolidtimeConfig(**data["solidtime"]),
            everhour=EverhourConfig(**data.get("everhour", {})),
            sync=SyncConfig(**data.get("sync", {})),
            mappings=Mappings(**data.get("mappings", {})),
        )

    def save_mappings(self, path: str | None = None) -> None:
        if path is None:
            path = os.environ.get("CONFIG_PATH", "config.json")

        config_path = Path(path)
        with open(config_path) as f:
            data = json.load(f)

        data["mappings"] = {
            "projects": self.mappings.projects,
            "tasks": self.mappings.tasks,
            "time_entries": self.mappings.time_entries,
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
