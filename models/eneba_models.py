from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProductNode(BaseModel):
    id: UUID
    name: str
    slug: str
    is_sellable: bool = Field(alias="isSellable")


class ProductEdge(BaseModel):
    node: ProductNode


class ProductConnection(BaseModel):
    edges: List[ProductEdge]


class SProductsData(BaseModel):
    s_products: ProductConnection = Field(alias="S_products")


class SProductsGraphQLResponse(BaseModel):
    data: SProductsData


class Price(BaseModel):
    amount: int
    currency: str
    price_no_commission: Optional[float] = None
    old_price_with_commission: Optional[float] = None


class CompetitionNode(BaseModel):
    is_in_stock: bool = Field(alias="isInStock")
    merchant_name: str = Field(alias="merchantName")
    belongs_to_you: bool = Field(alias="belongsToYou")
    price: Price


class CompetitionEdge(BaseModel):
    node: CompetitionNode


class CompetitionData(BaseModel):
    total_count: int = Field(alias="totalCount")
    edges: List[CompetitionEdge]


class CompetitionResult(BaseModel):
    product_id: UUID = Field(alias="productId")
    competition: CompetitionData


class SCompetitionData(BaseModel):
    s_competition: List[CompetitionResult] = Field(alias="S_competition")


class SCompetitionGraphQLResponse(BaseModel):
    data: SCompetitionData


class CalculatedPrice(BaseModel):
    price_with_commission: Price = Field(alias="priceWithCommission")
    price_without_commission: Price = Field(alias="priceWithoutCommission")


class SCalculatePriceData(BaseModel):
    s_calculate_price: CalculatedPrice = Field(alias="S_calculatePrice")


class SCalculatePriceGraphQLResponse(BaseModel):
    data: SCalculatePriceData


class PriceInput(BaseModel):
    amount: int
    currency: str


class CalculatePriceInput(BaseModel):
    product_id: str = Field(alias="productId")
    price: PriceInput


class UpdateAuctionInput(BaseModel):
    id: UUID
    price_i_want_to_get: PriceInput = Field(alias="priceIWantToGet")


class UpdateAuctionPayload(BaseModel):
    success: bool
    action_id: UUID = Field(alias="actionId")
    price_changed: bool = Field(alias="priceChanged")
    paid_for_price_change: bool = Field(alias="paidForPriceChange")


class SUpdateAuctionData(BaseModel):
    s_update_auction: UpdateAuctionPayload = Field(alias="S_updateAuction")


class SUpdateAuctionGraphQLResponse(BaseModel):
    data: SUpdateAuctionData
