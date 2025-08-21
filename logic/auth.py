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
        self.client_id = client_id

        self._initial_auth_payload = {
            "grant_type": "api_consumer",
            "client_id": client_id,
            "id": auth_id,
            "secret": auth_secret,
        }

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._client = httpx.Client()

    def get_auth_headers(self) -> Dict[str, str]:
        if not self._access_token or time.time() >= self._token_expires_at:
            self.logger.info("Token is invalid or expired.")

            if self._refresh_token:
                try:
                    self._refresh_token_flow()
                except ConnectionError:
                    self.logger.warning("Refresh token failed. Falling back to full authentication.")
                    self._get_new_token_from_credentials()
            else:
                self._get_new_token_from_credentials()

        return {"Authorization": f"Bearer {self._access_token}"}

    def _get_new_token_from_credentials(self) -> None:
        self.logger.info("Requesting new token using credentials...")
        self._perform_token_request(self._initial_auth_payload)

    def _refresh_token_flow(self) -> None:
        self.logger.info("Requesting new token using refresh token...")
        refresh_payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self.client_id,
        }
        self._perform_token_request(refresh_payload)

    def _perform_token_request(self, payload: Dict[str, str]) -> None:
        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            headers.update({"X-Proxy-Secret": "embeiuquadi"})
            response = self._client.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()

            token_data = AccessTokenResponse.model_validate(response.json())

            self._access_token = token_data.access_token
            self._token_expires_at = time.time() + token_data.expires_in - 60  # Trừ 60s an toàn

            if token_data.refresh_token:
                self._refresh_token = token_data.refresh_token
                self.logger.info("New access token and refresh token acquired.")
            else:
                self.logger.info("New access token acquired (no new refresh token provided).")

        except httpx.HTTPStatusError as e:
            self.logger.error(f"Token request failed: {e.response.status_code} - {e.response.text}")
            raise ConnectionError("Failed to perform token request.") from e

    def close(self):
        self._client.close()