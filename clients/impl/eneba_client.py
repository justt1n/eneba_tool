# eneba_client.py
import logging
from typing import List
from uuid import UUID

from clients.base_graphql_client import BaseGraphQLClient
from clients.impl.eneba_query import S_PRODUCTS_BY_SLUGS_QUERY, S_COMPETITION_QUERY
from logic.auth import EnebaAuthHandler
from models.eneba_models import SProductsGraphQLResponse, SCompetitionGraphQLResponse
from utils.config import settings


class EnebaClient:

    def __init__(self):
        graphql_url = settings.BASE_URL

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing EnebaClient for proxy...")

        auth_handler = EnebaAuthHandler()

        self._client = BaseGraphQLClient(
            graphql_url=graphql_url,
            auth_handler=auth_handler
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_product_by_slug(self, slugs: str) -> SProductsGraphQLResponse:
        variables = {
            "slugs": [slugs],
            "sort": "CREATED_AT_DESC",
            "first": 1
        }

        response_json = self._client.execute(
            query=S_PRODUCTS_BY_SLUGS_QUERY,
            variables=variables
        )

        return SProductsGraphQLResponse.model_validate(response_json)

    def get_competition_by_product_id(self, product_id: UUID) -> SCompetitionGraphQLResponse:
        product_id_str = str(product_id)

        variables = {
            "productIds": product_id_str,
        }

        response_json = self._client.execute(query=S_COMPETITION_QUERY, variables=variables)
        return SCompetitionGraphQLResponse.model_validate(response_json)
