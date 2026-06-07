"""Configuración por entorno del suscriptor (sin secretos en el repo)."""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.odm_api_url = os.getenv("ODM_API_URL", "")
        self.odm_webhook_secret = os.getenv("ODM_WEBHOOK_SECRET", "")
        self.ckan_url = os.getenv("CKAN_URL", "")
        self.ckan_api_token = os.getenv("CKAN_API_TOKEN", "")

    @property
    def ckan_configured(self) -> bool:
        return bool(self.ckan_url and self.ckan_api_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
