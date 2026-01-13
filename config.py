"""Configuration management for Atlas importer"""

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class AtlasConfig:
    """Atlas REST API configuration"""
    base_url: str
    username: str
    password: str
    verify_ssl: bool
    timeout: int


@dataclass
class ImportConfig:
    """CSV import configuration"""
    csv_file: str
    dry_run: bool
    log_level: str
    log_file: str


@dataclass
class RelationshipsConfig:
    """Relationship type configuration"""
    bidirectional_types: list
    unidirectional_types: list


@dataclass
class Config:
    """Complete application configuration"""
    atlas: AtlasConfig
    import_config: ImportConfig
    relationships: RelationshipsConfig

    @classmethod
    def from_file(cls, config_path: str = "config.yaml") -> "Config":
        """Load configuration from YAML file"""
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        return cls(
            atlas=AtlasConfig(**data["atlas"]),
            import_config=ImportConfig(**data["import"]),
            relationships=RelationshipsConfig(**data["relationships"]),
        )

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return Config(
            atlas=AtlasConfig(
                base_url=os.getenv("ATLAS_BASE_URL", "http://localhost:21000"),
                username=os.getenv("ATLAS_USERNAME", "admin"),
                password=os.getenv("ATLAS_PASSWORD", "admin"),
                verify_ssl=os.getenv("ATLAS_VERIFY_SSL", "true").lower() == "true",
                timeout=int(os.getenv("ATLAS_TIMEOUT", "30")),
            ),
            import_config=ImportConfig(
                csv_file=os.getenv("CSV_FILE", "example_glossary.csv"),
                dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                log_file=os.getenv("LOG_FILE", "atlas_import.log"),
            ),
            relationships=RelationshipsConfig(
                bidirectional_types=[
                    "synonym",
                    "antonym",
                    "related_term",
                    "see_also",
                ],
                unidirectional_types=[
                    "preferred_term",
                    "replacement_term",
                    "is_a",
                    "classifies",
                ],
            ),
        )
