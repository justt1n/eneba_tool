from typing import List
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
