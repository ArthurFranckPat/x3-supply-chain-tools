"""
Client Sage X3 — Web API SData.

Configure via .env :
    X3_BASE_URL   — URL racine (ex: http://host:port/api1/x3/erp/ENDPOINT)
    X3_USERNAME   — Utilisateur X3
    X3_PASSWORD   — Mot de passe
"""

import base64
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.hermes/.env"))


def _basic_auth_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


class X3Client:
    """Client pour la WEB API Sage X3 (SData 2.0 / REST)."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("X3_BASE_URL", "")).rstrip("/")
        self.username = username or os.getenv("X3_USERNAME", "")
        self.password = password or os.getenv("X3_PASSWORD", "")
        if not self.base_url:
            raise RuntimeError("X3_BASE_URL manquant")
        if not self.username:
            raise RuntimeError("X3_USERNAME manquant")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={
                "Authorization": _basic_auth_header(self.username, self.password),
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def query(
        self,
        classe: str,
        representation: str,
        where: str | list[str] | None = None,
        order_by: str | None = None,
        count: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Requête $query sur une classe X3."""
        url = f"{self.base_url}/{classe}?representation={representation}.$query"

        if where:
            if isinstance(where, list):
                where = " and ".join(where)
            url += f"&where={where}"
        if order_by:
            url += f"&orderBy={order_by}"
        if count is not None:
            url += f"&count={count}"
        if offset is not None:
            url += f"&offset={offset}"

        with self._client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def detail(
        self,
        classe: str,
        key: str,
        representation: str,
    ) -> dict[str, Any]:
        """Lit un enregistrement via $details."""
        url = f"{self.base_url}/{classe}('{key}')"
        params = {"representation": f"{representation}.$details"}

        with self._client() as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def query_all(
        self,
        classe: str,
        representation: str,
        where: str | list[str] | None = None,
        order_by: str | None = None,
        count: int | None = None,
    ) -> list[dict[str, Any]]:
        """Requête $query paginée — retourne toutes les pages."""
        items: list[dict[str, Any]] = []
        next_url: str | None = None

        with self._client() as client:
            while True:
                if next_url is None:
                    url = (
                        f"{self.base_url}/{classe}"
                        f"?representation={representation}.$query"
                    )
                    if where:
                        if isinstance(where, list):
                            where_str = " and ".join(where)
                        else:
                            where_str = where
                        url += f"&where={where_str}"
                    if order_by:
                        url += f"&orderBy={order_by}"
                    if count is not None:
                        url += f"&count={count}"
                    resp = client.get(url)
                else:
                    # Préserver le count dans l'URL de pagination
                    if count is not None and f"count=" not in next_url:
                        sep = "&" if "?" in next_url else "?"
                        next_url = f"{next_url}{sep}count={count}"
                    resp = client.get(next_url)
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("$resources", []))
                links = data.get("$links", {})
                next_url = links.get("$next", {}).get("$url")
                if not next_url:
                    break
        return items
