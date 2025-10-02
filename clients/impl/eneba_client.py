# eneba_client.py
import logging
from uuid import UUID

from clients.base_graphql_client import BaseGraphQLClient
from clients.impl.eneba_query import S_PRODUCTS_BY_SLUGS_QUERY, S_COMPETITION_QUERY, S_CALCULATE_PRICE_QUERY, \
    S_UPDATE_AUCTION_MUTATION, S_STOCK_QUERY
from logic.auth import EnebaAuthHandler
from models.eneba_models import SProductsGraphQLResponse, SCompetitionGraphQLResponse, SCalculatePriceGraphQLResponse, \
    PriceInput, CalculatePriceInput, UpdateAuctionInput, SUpdateAuctionGraphQLResponse, SStockGraphQLResponse
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

    def calculate_price(
        self,
        product_id: str,
        amount: int,
        currency: str = "EUR"
    ) -> SCalculatePriceGraphQLResponse:
        price_input = PriceInput(amount=amount, currency=currency)
        input_data = CalculatePriceInput(productId=product_id, price=price_input)

        variables = {
            "input": input_data.model_dump(by_alias=True)
        }

        response_json = self._client.execute(
            query=S_CALCULATE_PRICE_QUERY,
            variables=variables
        )

        return SCalculatePriceGraphQLResponse.model_validate(response_json)

    def update_auction(
        self,
        auction_id: str,
        amount: int,
        currency: str = "EUR"
    ) -> SUpdateAuctionGraphQLResponse:
        price_input = PriceInput(amount=amount, currency=currency)
        input_data = UpdateAuctionInput(id=auction_id, priceIWantToGet=price_input)

        variables = {
            "input": input_data.model_dump(by_alias=True)
        }

        response_json = self._client.execute(
            query=S_UPDATE_AUCTION_MUTATION,
            variables=variables
        )

        return SUpdateAuctionGraphQLResponse.model_validate(response_json)

    def get_stock_info(self, stock_id: UUID) -> SStockGraphQLResponse:
        self.logger.info(f"Fetching stock info for ID: {stock_id}")

        variables = {
            "stockId": str(stock_id)
        }

        response_json = self._client.execute(
            query=S_STOCK_QUERY,
            variables=variables
        )

        return SStockGraphQLResponse.model_validate(response_json)
