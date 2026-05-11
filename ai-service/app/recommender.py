from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

import pandas as pd
from unidecode import unidecode

from .graph_store import GraphStore
from .rag_engine import RAGEngine
from .sequence_model import SequenceModel
from .vector_store import VectorStore

ACTION_WEIGHTS = {
    "view": 1.0,
    "click": 2.0,
    "search": 1.3,
    "add_to_cart": 3.5,
    "wishlist": 1.7,
    "compare": 0.9,
    "purchase": 5.0,
}

BOOK_CATEGORIES = {"textbook", "novel"}
ELECTRONICS_CATEGORIES = {"mobile", "laptop", "refrigerator", "air_conditioner", "smartwatch"}
FASHION_CATEGORIES = {"shirt", "pants", "shoes"}

KEYWORD_TO_CATEGORY = {
    "laptop": "laptop",
    "máy tính": "laptop",
    "may tinh": "laptop",
    "điện thoại": "mobile",
    "dien thoai": "mobile",
    "mobile": "mobile",
    "tv": "electronics",
    "smartwatch": "smartwatch",
    "đồng hồ": "smartwatch",
    "dong ho": "smartwatch",
    "áo": "shirt",
    "ao": "shirt",
    "shirt": "shirt",
    "quần": "pants",
    "quan": "pants",
    "pants": "pants",
    "giày": "shoes",
    "giay": "shoes",
    "shoes": "shoes",
    "sách": "textbook",
    "sach": "textbook",
    "book": "book",
    "tu lanh": "refrigerator",
    "tủ lạnh": "refrigerator",
    "refrigerator": "refrigerator",
    "air conditioner": "air_conditioner",
    "dieu hoa": "air_conditioner",
    "điều hòa": "air_conditioner",
    "electronics": "electronics",
}

BUDGET_KEYWORDS = {"rẻ", "re", "tiết kiệm", "tiet kiem", "giá tốt", "gia tot", "cheap", "under"}
PRICE_KEYWORDS = {"gia", "price", "cost", "budget", "dong", "vnd"}
WARRANTY_KEYWORDS = {"warranty", "bao hanh", "baohanh", "bảo hành", "bao-hanh"}
BOOK_KEYWORDS = {"book", "sach", "sách", "textbook", "novel"}
ELECTRONICS_KEYWORDS = {"electronics", "dien tu", "điện tử", "air conditioner", "refrigerator", "laptop", "mobile", "smartwatch", "tv"}

COLOR_KEYWORDS = {
    "den": "black",
    "black": "black",
    "trang": "white",
    "white": "white",
    "do": "red",
    "red": "red",
    "xanh": "blue",
    "blue": "blue",
    "vang": "yellow",
    "yellow": "yellow",
    "xam": "gray",
    "gray": "gray",
    "grey": "gray",
    "nau": "brown",
    "brown": "brown",
    "hong": "pink",
    "pink": "pink",
}

SIZE_KEYWORDS = {"s": "s", "m": "m", "l": "l", "xl": "xl", "xxl": "xxl"}


@dataclass
class RecommendationResult:
    product_id: int
    name: str
    category: Optional[str]
    price: Optional[float]
    stock: Optional[int]
    score: float
    reasons: list[str]


@dataclass
class ParsedQueryFilters:
    category: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_warranty: Optional[float] = None
    max_warranty: Optional[float] = None


class HybridRecommender:
    def __init__(
        self,
        behavior_df: pd.DataFrame,
        products_df: pd.DataFrame,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "neo4jpass",
    ):
        self.behavior_df = behavior_df.copy()
        self.products_df = products_df.copy()
        self.products_df = self.products_df.drop_duplicates(subset=["id"]).fillna("")
        self.products_df["search_text"] = self.products_df.apply(self._build_search_text, axis=1)
        self.electronics_brand_terms = self._collect_catalog_terms("electronics_brand")
        self.book_author_terms = self._collect_catalog_terms("book_author")
        self.book_publisher_terms = self._collect_catalog_terms("book_publisher")
        self.user_histories = self._build_user_histories()
        self.user_item_scores = self._build_user_item_scores()
        self.popularity_scores = self._build_popularity_scores()
        self.sequence_model = SequenceModel(self.behavior_df)
        self.sequence_model.train()
        self.vector_store = VectorStore(self.products_df)
        self.graph_store = GraphStore(self.behavior_df, neo4j_uri=neo4j_uri, neo4j_user=neo4j_user, neo4j_password=neo4j_password)
        self.graph_synced = self.graph_store.ingest_to_neo4j(self.products_df)
        self.rag_engine = RAGEngine()

    def _build_search_text(self, row: pd.Series) -> str:
        parts = [str(row.get("name", "")), str(row.get("category_name", ""))]
        if row.get("book_author"):
            parts.append(str(row.get("book_author")))
        if row.get("book_publisher"):
            parts.append(str(row.get("book_publisher")))
        if row.get("electronics_brand"):
            parts.append(str(row.get("electronics_brand")))
        if row.get("electronics_warranty"):
            parts.append(str(row.get("electronics_warranty")))
        if row.get("fashion_color"):
            parts.append(str(row.get("fashion_color")))
        if row.get("fashion_size"):
            parts.append(str(row.get("fashion_size")))
        return " ".join(part for part in parts if part).lower()

    def _collect_catalog_terms(self, column_name: str) -> dict[str, str]:
        if column_name not in self.products_df.columns or self.products_df.empty:
            return {}
        terms: dict[str, str] = {}
        for raw_value in self.products_df[column_name].astype(str).tolist():
            cleaned = raw_value.strip()
            if not cleaned:
                continue
            terms[self._normalize_text(cleaned)] = cleaned
        return terms

    def _build_user_histories(self) -> dict[int, list[int]]:
        if self.behavior_df.empty:
            return {}
        ordered = self.behavior_df.sort_values(["user_id", "timestamp", "product_id"]).copy()
        histories: dict[int, list[int]] = {}
        for user_id, group in ordered.groupby("user_id"):
            histories[int(user_id)] = group["product_id"].astype(int).tolist()
        return histories

    def _build_user_item_scores(self) -> dict[int, dict[int, float]]:
        scores: dict[int, dict[int, float]] = {}
        if self.behavior_df.empty:
            return scores
        df = self.behavior_df.copy()
        df["weight"] = df["action"].map(ACTION_WEIGHTS).fillna(1.0)
        grouped = df.groupby(["user_id", "product_id"], as_index=False)["weight"].sum()
        for row in grouped.itertuples(index=False):
            scores.setdefault(int(row.user_id), {})[int(row.product_id)] = float(row.weight)
        return scores

    def _build_popularity_scores(self) -> dict[int, float]:
        if self.behavior_df.empty:
            return {}
        df = self.behavior_df.copy()
        df["weight"] = df["action"].map(ACTION_WEIGHTS).fillna(1.0)
        popularity = df.groupby("product_id", as_index=False)["weight"].sum()
        max_weight = float(popularity["weight"].max() or 1.0)
        return {int(row.product_id): float(row.weight) / max_weight for row in popularity.itertuples(index=False)}

    def _filter_seen(self, user_id: int, candidates: list[int]) -> list[int]:
        seen = set(self.user_item_scores.get(user_id, {}).keys())
        return [product_id for product_id in candidates if product_id not in seen]

    def _normalize_text(self, text: str) -> str:
        return unidecode((text or "").lower().strip())

    def _semantic_scores(self, query: str) -> dict[int, float]:
        rows = self.vector_store.search(self._normalize_text(query), top_k=30)
        return {pid: score for pid, score in rows}

    def _extract_category_hint(self, query: str) -> Optional[str]:
        normalized = self._normalize_text(query)
        for keyword, category in KEYWORD_TO_CATEGORY.items():
            if self._normalize_text(keyword) in normalized:
                return category
        return None

    def _extract_fashion_attributes(self, query: str) -> dict[str, Optional[str]]:
        normalized = self._normalize_text(query)
        compact = normalized.replace(" ", "")

        color: Optional[str] = None
        for keyword, mapped_color in COLOR_KEYWORDS.items():
            if keyword in normalized or keyword in compact:
                color = mapped_color
                break

        size: Optional[str] = None
        for keyword, mapped_size in SIZE_KEYWORDS.items():
            if f" {keyword} " in f" {normalized} " or compact.endswith(keyword):
                size = mapped_size
                break

        return {"color": color, "size": size}

    def _extract_catalog_value(self, query: str, terms: dict[str, str]) -> Optional[str]:
        normalized = self._normalize_text(query)
        compact = normalized.replace(" ", "")
        for candidate, original in terms.items():
            candidate_norm = self._normalize_text(candidate)
            if candidate_norm and (candidate_norm in normalized or candidate_norm.replace(" ", "") in compact):
                return original
        return None

    def _parse_price_number(self, value: str) -> Optional[float]:
        cleaned = self._normalize_text(value).replace(",", ".")
        match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if not match:
            return None
        return float(match.group(1))

    def _extract_price_bounds(self, query: str) -> tuple[Optional[float], Optional[float]]:
        normalized = self._normalize_text(query)
        compact = normalized.replace(" ", "")

        range_patterns = [
            r"(?:tu|from)\s+(\d+(?:[.,]\d+)?)\s+(?:den|to|and|-)\s+(\d+(?:[.,]\d+)?)",
            r"(?:khoang|between)\s+(\d+(?:[.,]\d+)?)\s+(?:den|to|and|-)\s+(\d+(?:[.,]\d+)?)",
        ]
        for pattern in range_patterns:
            match = re.search(pattern, normalized)
            if match:
                lower = float(match.group(1).replace(",", "."))
                upper = float(match.group(2).replace(",", "."))
                return min(lower, upper), max(lower, upper)

        upper_patterns = [
            r"(?:duoi|<=|less than|under|below|nho hon|thap hon)\s+(\d+(?:[.,]\d+)?)",
        ]
        for pattern in upper_patterns:
            match = re.search(pattern, normalized)
            if match:
                return None, float(match.group(1).replace(",", "."))

        lower_patterns = [
            r"(?:tren|>=|more than|over|above|lon hon|cao hon)\s+(\d+(?:[.,]\d+)?)",
        ]
        for pattern in lower_patterns:
            match = re.search(pattern, normalized)
            if match:
                return float(match.group(1).replace(",", ".")), None

        number_match = re.search(r"(\d+(?:[.,]\d+)?)", normalized)
        if number_match and any(keyword in normalized for keyword in PRICE_KEYWORDS):
            value = float(number_match.group(1).replace(",", "."))
            if any(keyword in normalized for keyword in {"duoi", "under", "below", "nho hon", "thap hon"}):
                return None, value
            if any(keyword in normalized for keyword in {"tren", "over", "above", "lon hon", "cao hon", ">=", "more than"}):
                return value, None
        return None, None

    def _extract_warranty_bounds(self, query: str) -> tuple[Optional[float], Optional[float]]:
        normalized = self._normalize_text(query)
        if not any(keyword in normalized for keyword in WARRANTY_KEYWORDS):
            return None, None
        return self._extract_price_bounds(query)

    def _category_matches(self, category: str, query_category: Optional[str]) -> bool:
        if not query_category:
            return True
        if query_category == "electronics":
            return category in ELECTRONICS_CATEGORIES
        if query_category == "book":
            return category in BOOK_CATEGORIES
        if query_category == "fashion":
            return category in FASHION_CATEGORIES
        return category == query_category

    def _extract_filters(self, query: str) -> ParsedQueryFilters:
        category_hint = self._extract_category_hint(query)
        fashion_attrs = self._extract_fashion_attributes(query)
        brand = self._extract_catalog_value(query, self.electronics_brand_terms)
        author = self._extract_catalog_value(query, self.book_author_terms)
        publisher = self._extract_catalog_value(query, self.book_publisher_terms)

        normalized = self._normalize_text(query)
        min_price, max_price = (None, None)
        min_warranty, max_warranty = (None, None)

        if any(keyword in normalized for keyword in WARRANTY_KEYWORDS) or category_hint == "electronics":
            min_warranty, max_warranty = self._extract_warranty_bounds(query)

        if not any(keyword in normalized for keyword in WARRANTY_KEYWORDS) and (
            any(keyword in normalized for keyword in PRICE_KEYWORDS)
            or any(keyword in normalized for keyword in {"duoi", "tren", "khoang", "from", "between", "under", "over", "above", "below"})
        ):
            min_price, max_price = self._extract_price_bounds(query)

        if min_price is None and max_price is None and not any(keyword in normalized for keyword in WARRANTY_KEYWORDS):
            if any(keyword in normalized for keyword in PRICE_KEYWORDS):
                min_price, max_price = self._extract_price_bounds(query)

        return ParsedQueryFilters(
            category=category_hint,
            color=fashion_attrs["color"],
            size=fashion_attrs["size"],
            brand=brand,
            author=author,
            publisher=publisher,
            min_price=min_price,
            max_price=max_price,
            min_warranty=min_warranty,
            max_warranty=max_warranty,
        )

    def _product_matches_filters(self, row: pd.Series, filters: ParsedQueryFilters) -> bool:
        category = str(row.get("category_name", "")).strip().lower()
        if not self._category_matches(category, filters.category):
            return False

        if filters.color:
            color_value = self._normalize_text(str(row.get("fashion_color", "")))
            if filters.color not in color_value:
                return False

        if filters.size:
            if str(row.get("fashion_size", "")).strip().lower() != filters.size:
                return False

        if filters.brand:
            brand_value = self._normalize_text(str(row.get("electronics_brand", "")))
            if filters.brand.lower() != str(row.get("electronics_brand", "")).strip().lower() and filters.brand not in brand_value:
                return False

        if filters.author:
            author_value = self._normalize_text(str(row.get("book_author", "")))
            if filters.author.lower() != str(row.get("book_author", "")).strip().lower() and filters.author not in author_value:
                return False

        if filters.publisher:
            publisher_value = self._normalize_text(str(row.get("book_publisher", "")))
            if filters.publisher.lower() != str(row.get("book_publisher", "")).strip().lower() and filters.publisher not in publisher_value:
                return False

        if filters.min_price is not None or filters.max_price is not None:
            price = float(row.get("price", 0.0) or 0.0)
            if filters.min_price is not None and price < filters.min_price:
                return False
            if filters.max_price is not None and price > filters.max_price:
                return False

        if filters.min_warranty is not None or filters.max_warranty is not None:
            warranty_raw = row.get("electronics_warranty", "")
            try:
                warranty = float(warranty_raw)
            except (TypeError, ValueError):
                return False
            if filters.min_warranty is not None and warranty < filters.min_warranty:
                return False
            if filters.max_warranty is not None and warranty > filters.max_warranty:
                return False

        return True

    def _query_intent(self, query: str) -> str:
        lowered = self._normalize_text(query)
        if any(keyword in lowered for keyword in BUDGET_KEYWORDS):
            return "budget"
        if self._extract_category_hint(lowered):
            return "category_search"
        if any(word in lowered for word in ["tu van", "goi y", "recommend", "tu van", "chatbot"]):
            return "advice"
        return "general"

    def recommend(self, user_id: int, limit: int = 5, query: Optional[str] = None) -> tuple[list[RecommendationResult], dict[str, float], str]:
        if self.products_df.empty:
            return [], {"behavior": 0.35, "sequence": 0.25, "graph": 0.20, "semantic": 0.20}, "no_products"

        user_id = int(user_id)
        query = (query or "").strip()
        intent = self._query_intent(query) if query else "personalized"
        filters = self._extract_filters(query) if query else ParsedQueryFilters()
        history = self.user_histories.get(user_id, [])
        all_product_ids = self.products_df["id"].astype(int).tolist()
        candidate_ids = self._filter_seen(user_id, all_product_ids) or all_product_ids
        category_ids: list[int] = []
        if filters.category:
            category_ids = [
                int(row_id)
                for row_id, row in self.products_df.set_index("id").iterrows()
                if self._category_matches(str(row.get("category_name", "")).strip().lower(), filters.category)
            ]
        filtered_ids = [
            int(row_id)
            for row_id, row in self.products_df.set_index("id").iterrows()
            if self._product_matches_filters(row, filters)
        ]
        if filtered_ids:
            candidate_ids = [pid for pid in candidate_ids if pid in filtered_ids]
            if not candidate_ids:
                candidate_ids = filtered_ids
        elif category_ids:
            candidate_ids = [pid for pid in candidate_ids if pid in category_ids]
            if not candidate_ids:
                candidate_ids = category_ids

        semantic_scores = self._semantic_scores(query)
        sequence_scores = self.sequence_model.predict_scores(history, top_k=50)
        recommendations: list[RecommendationResult] = []

        for product_id in candidate_ids:
            behavior_score = self.user_item_scores.get(user_id, {}).get(product_id, 0.0)
            graph_score = 0.0
            sequence_score = sequence_scores.get(product_id, 0.0)
            reasons: list[str] = []

            for seen_product_id, seen_weight in self.user_item_scores.get(user_id, {}).items():
                similars = self.graph_store.similar_products(seen_product_id, top_k=20)
                for sim_pid, sim_score in similars:
                    if sim_pid == product_id and sim_score > graph_score:
                        graph_score = sim_score
                        reasons = [f"Graph similar to product #{seen_product_id}"]
                behavior_score = max(behavior_score, seen_weight)

            semantic_score = semantic_scores.get(product_id, 0.0)
            popularity_score = self.popularity_scores.get(product_id, 0.0)
            score = (0.30 * behavior_score) + (0.25 * sequence_score) + (0.20 * graph_score) + (0.20 * semantic_score) + (0.05 * popularity_score)

            product_row = self.products_df[self.products_df["id"].astype(int) == int(product_id)].iloc[0]
            price = float(product_row.get("price", 0.0)) if product_row.get("price", "") != "" else 0.0
            if intent == "budget" and price > 0:
                budget_penalty = min(price / 1000.0, 2.5)
                score -= 0.15 * budget_penalty
            if filters.min_price is not None or filters.max_price is not None:
                score += 0.2
            if filters.min_warranty is not None or filters.max_warranty is not None:
                score += 0.2

            if semantic_score > 0.10:
                reasons.append("Query match")
            if filters.color and filters.color in self._normalize_text(str(product_row.get("fashion_color", ""))):
                reasons.append(f"Color match: {filters.color}")
            if filters.size and str(product_row.get("fashion_size", "")).strip().lower() == filters.size:
                reasons.append(f"Size match: {filters.size}")
            if filters.brand and filters.brand.lower() in self._normalize_text(str(product_row.get("electronics_brand", ""))):
                reasons.append(f"Brand match: {filters.brand}")
            if filters.author and filters.author.lower() in self._normalize_text(str(product_row.get("book_author", ""))):
                reasons.append(f"Author match: {filters.author}")
            if filters.publisher and filters.publisher.lower() in self._normalize_text(str(product_row.get("book_publisher", ""))):
                reasons.append(f"Publisher match: {filters.publisher}")
            if filters.min_warranty is not None or filters.max_warranty is not None:
                reasons.append("Warranty match")
            if filters.min_price is not None or filters.max_price is not None:
                reasons.append("Price range match")
            if popularity_score > 0.6:
                reasons.append("Popular product")
            if sequence_score > 0.05:
                reasons.append("Sequence prediction")
            if not reasons:
                reasons.append("Hybrid score")

            recommendations.append(
                RecommendationResult(
                    product_id=int(product_row["id"]),
                    name=str(product_row.get("name", "")),
                    category=str(product_row.get("category_name", "")) or None,
                    price=price,
                    stock=int(product_row.get("stock", 0)) if product_row.get("stock", "") != "" else None,
                    score=float(score),
                    reasons=reasons[:3],
                )
            )

        if intent == "budget":
            recommendations.sort(key=lambda item: (item.score, -(item.price or 0.0)), reverse=True)
            recommendations = sorted(recommendations, key=lambda item: (-(item.score), item.price or 0.0))
        else:
            recommendations.sort(key=lambda item: item.score, reverse=True)

        return recommendations[:limit], {"behavior": 0.30, "sequence": 0.25, "graph": 0.20, "semantic": 0.20, "popularity": 0.05}, intent

    def chat(self, query: str, user_id: Optional[int] = None, limit: int = 5) -> tuple[str, list[RecommendationResult], str]:
        cleaned_query = query.strip()
        intent = self._query_intent(cleaned_query)
        recommendations, _, _ = self.recommend(user_id or 0, limit=limit, query=cleaned_query)
        answer = self.rag_engine.generate_answer(cleaned_query, intent, recommendations, user_id)
        return answer, recommendations, intent

    def summary(self) -> dict[str, object]:
        action_counts = self.behavior_df["action"].value_counts().to_dict() if not self.behavior_df.empty else {}
        return {
            "users": int(self.behavior_df["user_id"].nunique()) if not self.behavior_df.empty else 0,
            "events": int(len(self.behavior_df)),
            "products": int(self.products_df.shape[0]),
            "actions": action_counts,
            "sample_users": sorted(list(self.user_histories.keys()))[:10],
            "sequence_trained": self.sequence_model.trained,
            "sequence_rows": self.sequence_model.training_rows,
            "graph_synced": self.graph_synced,
        }
