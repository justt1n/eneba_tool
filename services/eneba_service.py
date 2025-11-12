import copy
import re
from typing import List
from uuid import UUID

from clients.impl.eneba_client import EnebaClient
from models.eneba_models import CompetitionEdge
from models.logic_models import AnalysisResult, CommissionPrice
from models.sheet_models import Payload


class EnebaService:
    def __init__(self, eneba_client: EnebaClient):
        self._client = eneba_client

    async def get_product_id_by_slug(self, slugs: str) -> UUID:
        res = await self._client.get_product_by_slug(slugs)
        try:
            response_data = res.data.s_products.edges
            if not response_data or len(response_data) == 0:
                raise ValueError(f"No products found for slug: {slugs}")
            return response_data[0].node.id
        except AttributeError as e:
            raise ValueError(f"Invalid response structure: {e}") from e

    async def get_competition_by_product_id(self, product_id: UUID) -> List[CompetitionEdge]:
        res = await self._client.get_competition_by_product_id(product_id)
        try:
            response_data = res.data.s_competition
            if not response_data or len(response_data) == 0:
                raise ValueError(f"No competition data found for product ID: {product_id}")
            return response_data[0].competition.edges
        except AttributeError as e:
            raise ValueError(f"Invalid response structure: {e}") from e

    async def get_competition_by_slug(self, slug: str) -> List[CompetitionEdge]:
        product_id = await self.get_product_id_by_slug(slug)
        if not product_id:
            raise ValueError(f"Product ID not found for slug: {slug}")

        products = await self.get_competition_by_product_id(product_id)
        if not products:
            raise ValueError(f"No competition data found for product ID: {product_id}")

        filtered_and_adjusted_products = []
        for product in products:
            if product.node.is_in_stock and product.node.price.amount > 0:
                product_copy = copy.deepcopy(product)
                product_copy.node.price.amount /= 100
                filtered_and_adjusted_products.append(product_copy)

        return filtered_and_adjusted_products

    def _filter_products_by_criteria(self, payload: Payload, products: List[CompetitionEdge]) -> List[CompetitionEdge]:
        """Filter products based on blacklist and price range criteria."""
        filtered_products = []
        for product in products:
            if product.node.merchant_name not in payload.fetched_black_list and product.node.price.amount > 0:
                if payload.fetched_min_price is not None and product.node.price.amount < payload.fetched_min_price:
                    continue
                if payload.fetched_max_price is not None and product.node.price.amount > payload.fetched_max_price:
                    continue
                filtered_products.append(product)
        return filtered_products

    async def enrich_products_with_commission(self, payload: Payload, products: List[CompetitionEdge], limit: int = 4) -> List[CompetitionEdge]:
        """Enrich first N products with commission price calculations."""
        for i, product in enumerate(products[:limit]):
            price_obj = await self.calculate_commission_price(payload.prod_uuid, product.node.price.amount)
            product.node.price.price_no_commission = price_obj.get_price_without_commission()
            product.node.price.old_price_with_commission = product.node.price.amount
            product.node.price.amount = price_obj.get_price_without_commission()
        return products

    async def _filter_products(self, payload: Payload, products: List[CompetitionEdge]) -> List[CompetitionEdge]:
        filtered_products = self._filter_products_by_criteria(payload, products)
        return filtered_products

    async def analyze_competition(self, payload: Payload, products: List[CompetitionEdge]) -> AnalysisResult:
        top_sellers_for_log = products[:4]
        sellers_below_min = []
        # Thêm await
        top_sellers_for_log = await self.enrich_products_with_commission(payload, top_sellers_for_log)
        filtered_products = await self._filter_products(payload, products)
        competitive_price = payload.fetched_max_price
        competitor_name = "Not found"
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

    async def calculate_commission_price(self, prodId: str, amount: float, currency: str = "EUR") -> CommissionPrice:
        price = int(amount * 100)
        res = await self._client.calculate_price(product_id=prodId, amount=price, currency=currency)
        commission_price = CommissionPrice(
            price_without_commission=res.data.s_calculate_price.price_without_commission.amount,
            price_with_commission=res.data.s_calculate_price.price_with_commission.amount,
        )
        try:
            return commission_price
        except AttributeError as e:
            raise ValueError(f"Invalid response structure: {e}") from e

    async def update_product_price(self, offer_id: str, new_price: float) -> bool:
        price = int(new_price * 100)
        res = await self._client.update_auction(auction_id=offer_id, amount=price)
        return res.data.s_update_auction.success

    async def check_next_free_in_minutes(self, payload: Payload) -> tuple[Payload, int, int] | tuple[int, int]:
        """
        Checks the time in minutes until the next free quota refresh.

        Args:
            prd_id: The ID of the stock (as a string).

        Returns:
            The number of minutes until the next free refresh.
            Returns 0 if the quota is fully recharged (nextFreeIn is null).

        Raises:
            ValueError: If prd_id has an invalid UUID format or the stock is not found.
        """
        prd_id = payload.product_id
        try:
            prd_id = prd_id.split('/')[-1]
            stock_uuid = UUID(prd_id)
        except ValueError:
            raise ValueError(f"'{prd_id}' is not a valid UUID format.")

        res = await self._client.get_stock_info(stock_uuid)

        try:
            quota_info = res.data.s_stock.edges[0].node.price_update_quota
            _price = res.data.s_stock.edges[0].node.price.amount
            _commission = res.data.s_stock.edges[0].node.commission.rate.amount if res.data.s_stock.edges[0].node.commission.rate.amount else 0
            payload.current_price = _price - _commission
            if payload.current_price > 0:
                payload.current_price = payload.current_price / 100
        except (IndexError, AttributeError):
            raise ValueError(f"No stock information found for ID: {prd_id}")

        # Handle the logic as requested
        if quota_info.next_free_in is None:
            # If nextFreeIn is null, return 0
            return payload, 0, quota_info.quota
        else:
            # If it has a value, convert from seconds to minutes (rounding down)
            return payload, quota_info.next_free_in // 60, 0

    # Hàm này không làm I/O, chỉ xử lý chuỗi, nên giữ nguyên là sync (đồng bộ)
    def get_offer_id_by_url(self, url: str) -> str:
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        match = re.search(pattern, url)
        if match:
            return match.group(0)
        else:
            raise ValueError(f"Invalid URL format, cannot extract offer ID: {url}")

    async def close(self):
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()