import logging
import time
from typing import Dict, Optional

import httpx

from models.eneba.oauth_models import AccessTokenResponse
from utils.config import settings


class EnebaAuthHandler:
    def __init__(
        self,
        auth_id: str,
        auth_secret: str,
        client_id: str,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token_url = settings.AUTH_URL

        self._auth_payload = {
            "grant_type": "api_consumer",
            "client_id": client_id,
            "id": auth_id,
            "secret": auth_secret,
        }

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._client = httpx.Client()

    def get_auth_headers(self) -> Dict[str, str]:
        if not self._access_token or time.time() >= self._token_expires_at:
            self.logger.info("Token is invalid or expired. Fetching a new one.")
            self._fetch_token()

        return {"Authorization": f"Bearer {self._access_token}"}

    def _fetch_token(self) -> None:
        self.logger.info("Requesting new access token from Eneba...")
        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = self._client.post(self.token_url, data=self._auth_payload, headers=headers)
            response.raise_for_status()

            token_data = AccessTokenResponse.model_validate(response.json())
            self._access_token = token_data.access_token
            self._token_expires_at = time.time() + token_data.expires_in - 60
            self.logger.info("New token acquired successfully.")

        except httpx.HTTPStatusError as e:
            self.logger.critical(f"Fatal: Could not authenticate with Eneba. {e.response.text}")
            raise ConnectionError("Failed to authenticate with Eneba API.") from e

    def close(self):
        self._client.close()
