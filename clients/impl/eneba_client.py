# eneba_client.py
import logging
from typing import Dict, Any

from clients.base_graphql_client import BaseGraphQLClient
from clients.impl.eneba_ import S_PRODUCTS_QUERY
from logic.auth import EnebaAuthHandler


class EnebaClient:

    def __init__(self, auth_id: str, auth_secret: str, client_id: str, sandbox: bool = True):
        auth_handler = EnebaAuthHandler(auth_id, auth_secret, client_id, sandbox)

        graphql_url = f"{auth_handler.base_url}/graphql/"

        self._client = BaseGraphQLClient(graphql_url=graphql_url, auth_handler=auth_handler)
        self.logger = logging.getLogger(self.__class__.__name__)


    def search_products(self, search: str, first: int = 10) -> SProductsGraphQLResponse:
        """Thực thi query tìm kiếm sản phẩm."""
        self.logger.info(f"Searching for products with phrase: '{search}'")
        variables = {"search": search, "first": first}
        response_json = self._client.execute(query=S_PRODUCTS_QUERY, variables=variables)
        return SProductsGraphQLResponse.model_validate(response_json)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()