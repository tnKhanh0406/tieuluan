from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    product_id: int
    name: str
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    score: float
    reasons: List[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    user_id: int
    limit: int
    query: Optional[str] = None
    intent: Optional[str] = None
    recommendations: List[RecommendationItem]
    strategy: dict[str, float]
    summary: str


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    user_id: Optional[int] = None
    limit: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    intent: str
    answer: str
    recommendations: List[RecommendationItem]


class TrackEventRequest(BaseModel):
    user_id: int
    product_id: int
    action: str = Field(pattern="^(view|click|search|add_to_cart|purchase|wishlist|compare)$")
    timestamp: int = Field(..., ge=0)
