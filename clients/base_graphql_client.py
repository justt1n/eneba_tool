import json
import logging
import re
from typing import Any, Dict, Optional

import httpx
from tenacity import stop_after_delay, retry, retry_if_exception, RetryCallState

from clients.exceptions import GraphQLError, GraphQLClientError


def _get_graphql_operation_name(query: str) -> str:
    match = re.search(r'\b(query|mutation)\s+([A-Za-z_][A-Za-z0-9_]*)', query or '')
    if match:
        return match.group(2)
    return "anonymous"


def _truncate_response_body(body: str, limit: int = 1000) -> str:
    body = (body or "").strip()
    if len(body) <= limit:
        return body
    return f"{body[:limit]}... (truncated, {len(body)} chars total)"


def _get_retry_after_seconds(retry_state: "RetryCallState") -> int:
    exception = retry_state.outcome.exception()
    if exception and isinstance(exception, GraphQLError):
        try:
            error_message = exception.errors[0].get('message', '')

            match = re.search(r'Retry after (\d+)', error_message)
            if match:
                seconds = int(match.group(1))
                logging.warning(f"Rate limit hit. Retrying after {seconds} seconds...")
                return seconds
        except (IndexError, KeyError, TypeError):
            pass
    if exception and isinstance(exception, GraphQLClientError):
        logging.warning(
            f"Transient Eneba GraphQL error. Retrying after 5 seconds: {exception}"
        )
    else:
        logging.warning("Rate limit hit. Retrying after 5 seconds (default)...")
    return 5


def _is_rate_limit_error(exception: BaseException) -> bool:
    if isinstance(exception, GraphQLError):
        try:
            error_message = exception.errors[0].get('message', '')
            return 'Too Many Requests' in error_message
        except (IndexError, KeyError, TypeError):
            return False
    if isinstance(exception, GraphQLClientError):
        if exception.status_code in {429, 502, 503, 504}:
            return True
        response_body = (exception.response_body or "").lower()
        return exception.status_code == 403 and (
            "just a moment" in response_body
            or "cloudflare" in response_body
            or "cf-browser-verification" in response_body
        )
    return False


class BaseGraphQLClient:

    def __init__(self, graphql_url: str, client: httpx.AsyncClient, auth_handler: Optional[Any] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not graphql_url:
            raise ValueError("GraphQL URL is required.")

        self.graphql_url = graphql_url
        self.auth_handler = auth_handler

        self._client = client

    @retry(
        stop=stop_after_delay(60),
        retry=retry_if_exception(_is_rate_limit_error),
        wait=_get_retry_after_seconds
    )
    async def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        headers.update({"X-Proxy-Secret": "embeiuquadi"})
        if self.auth_handler:
            auth_headers = self.auth_handler.get_auth_headers()
            headers.update(auth_headers)

        payload = {"query": query, "variables": variables or {}}
        operation_name = _get_graphql_operation_name(query)

        try:
            self.logger.debug(f"Executing GraphQL operation: {operation_name}")
            response = await self._client.post(self.graphql_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_json = response.json()
            if "errors" in response_json:
                raise GraphQLError(response_json["errors"])
            return response_json

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            try:
                error_json = json.loads(error_body)
                if "errors" in error_json:
                    raise GraphQLError(error_json["errors"])
            except json.JSONDecodeError:
                pass
            safe_error_body = _truncate_response_body(error_body)
            details = [
                f"HTTP {e.response.status_code}",
                f"operation={operation_name}",
                f"url={e.request.url}",
            ]
            if safe_error_body:
                details.append(f"response={safe_error_body}")

            if e.response.status_code == 403:
                details.append(
                    "hint=Forbidden. Check Eneba credentials/token, X-Proxy-Secret, proxy allowlist, or account permissions."
                )

            message = "Eneba GraphQL request failed: " + " | ".join(details)
            self.logger.error(message)
            raise GraphQLClientError(
                message,
                status_code=e.response.status_code,
                url=str(e.request.url),
                operation=operation_name,
                response_body=safe_error_body
            ) from e
        except httpx.RequestError as e:
            message = f"Eneba GraphQL network error: operation={operation_name} | url={e.request.url} | error={e}"
            self.logger.error(message)
            raise GraphQLClientError(
                message,
                url=str(e.request.url),
                operation=operation_name
            ) from e

    async def close(self):
        self.logger.info("Closing auth handler (client is managed externally).")
        if self.auth_handler and hasattr(self.auth_handler, 'close'):
            if hasattr(self.auth_handler, 'aclose'):
                await self.auth_handler.aclose()
            else:
                self.auth_handler.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
