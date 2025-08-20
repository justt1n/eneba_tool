# base_graphql_client.py
import logging
from typing import Any, Dict, Optional

import httpx

from clients.exceptions import GraphQLError, GraphQLClientError


class BaseGraphQLClient:

    def __init__(self, graphql_url: str, auth_handler: Optional[Any] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not graphql_url:
            raise ValueError("GraphQL URL is required.")

        self.graphql_url = graphql_url
        self.auth_handler = auth_handler
        self._client = httpx.Client()

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        headers.update({"X-Proxy-Secret": "embeiuquadi"})
        if self.auth_handler:
            auth_headers = self.auth_handler.get_auth_headers()
            headers.update(auth_headers)

        payload = {"query": query, "variables": variables or {}}

        try:
            self.logger.debug("Executing GraphQL query...")
            response = self._client.post(self.graphql_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_json = response.json()
            if "errors" in response_json:
                raise GraphQLError(response_json["errors"])
            return response_json

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise GraphQLClientError(f"HTTP Error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            self.logger.error(f"A network error occurred: {e}")
            raise GraphQLClientError("Network Error") from e

    def close(self):
        self.logger.info("Closing client and auth handler.")
        self._client.close()
        if self.auth_handler and hasattr(self.auth_handler, 'close'):
            self.auth_handler.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
