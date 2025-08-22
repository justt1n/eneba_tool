import copy
from typing import List
from uuid import UUID

from clients.impl.eneba_client import EnebaClient
from models.eneba_models import CompetitionEdge
from models.logic_models import AnalysisResult
from models.sheet_models import Payload


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

    def get_competition_by_slug(self, slug: str) -> List[CompetitionEdge]:
        product_id = self.get_product_id_by_slug(slug)
        if not product_id:
            raise ValueError(f"Product ID not found for slug: {slug}")

        products = self.get_competition_by_product_id(product_id)
        if not products:
            raise ValueError(f"No competition data found for product ID: {product_id}")

        filtered_and_adjusted_products = []
        for product in products:
            if product.node.is_in_stock and product.node.price.amount > 0:
                product_copy = copy.deepcopy(product)
                product_copy.node.price.amount /= 100
                filtered_and_adjusted_products.append(product_copy)

        return filtered_and_adjusted_products

    def _filter_products(self, payload: Payload, products: List[CompetitionEdge]) -> List[CompetitionNode]:
        filtered_products = []
        for product in products:
            if product.node.merchant_name not in payload.fetched_black_list and product.node.price.amount > 0:
                if payload.fetched_min_price is not None and product.node.price.amount < payload.fetched_min_price:
                    continue
                if payload.fetched_max_price is not None and product.node.price.amount > payload.fetched_max_price:
                    continue
                filtered_products.append(product)
        return filtered_products

    def analyze_competition(self, payload: Payload, products: List[CompetitionEdge]) -> AnalysisResult:
        top_sellers_for_log = products[:4]
        sellers_below_min = []
        filtered_products = self._filter_products(payload, products)
        competitive_price = payload.fetched_max_price
        competitor_name = "Not found, set max"
        if len(filtered_products) > 0:
            filtered_products.sort(key=lambda x: x.node.price.amount)
            competitive_price = filtered_products[0].node.price.amount
            competitor_name = filtered_products[0].node.merchant_name

            for product in filtered_products:
                if product.node.price.amount < payload.fetched_min_price:
                    sellers_below_min.append(product)

        return AnalysisResult(
            competitor_name=competitor_name,
            competitive_price=competitive_price,
            top_sellers_for_log=top_sellers_for_log,
            sellers_below_min=sellers_below_min
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
