# eneba_client.py
import logging

from clients.base_graphql_client import BaseGraphQLClient
from clients.impl.eneba_query import S_PRODUCTS_QUERY
from logic.auth import EnebaAuthHandler
from utils.config import settings


class EnebaClient:

    def __init__(
            self,
            auth_id: str,
            auth_secret: str,
            client_id: str,
            sandbox: bool = True
    ):
        graphql_url = settings.BASE_URL

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing EnebaClient for proxy...")

        auth_handler = EnebaAuthHandler(
            auth_id=auth_id,
            auth_secret=auth_secret,
            client_id=client_id,
        )

        self._client = BaseGraphQLClient(
            graphql_url=graphql_url,
            auth_handler=auth_handler
        )

    def search_products(self, search: str, first: int = 10) -> SProductsGraphQLResponse:
        variables = {"search": search, "first": first}

        response_json = self._client.execute(
            query=S_PRODUCTS_QUERY,
            variables=variables
        )

        return SProductsGraphQLResponse.model_validate(response_json)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
