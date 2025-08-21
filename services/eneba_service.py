from typing import List
from uuid import UUID

from clients.impl.eneba_client import EnebaClient
from models.eneba_models import CompetitionEdge


class EnebaService:
    def __init__(self, eneba_client: EnebaClient):
        self._client = eneba_client

    def get_product_id_by_slug(self, slugs: str) -> UUID:
        res = self._client.get_product_by_slug(slugs)
        try:
            response_data = res.data.s_products.edges
            if not response_data or len(response_data) == 0:
                raise ValueError(f"No products found for slug: {slugs}")
            return response_data[0].node.id
        except AttributeError as e:
            raise ValueError(f"Invalid response structure: {e}") from e

    def get_competition_by_product_id(self, product_id: UUID) -> List[CompetitionEdge]:
        res = self._client.get_competition_by_product_id(product_id)
        try:
            response_data = res.data.s_competition
            if not response_data or len(response_data) == 0:
                raise ValueError(f"No competition data found for product ID: {product_id}")
            return response_data[0].competition.edges
        except AttributeError as e:
            raise ValueError(f"Invalid response structure: {e}") from e

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
