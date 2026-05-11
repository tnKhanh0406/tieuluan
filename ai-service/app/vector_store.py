from __future__ import annotations

from typing import Optional

import faiss
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


class VectorStore:
    def __init__(self, products_df: pd.DataFrame):
        self.products_df = products_df.copy()
        self.products_df = self.products_df.drop_duplicates(subset=["id"]).fillna("")
        self.products_df["search_text"] = self.products_df.apply(self._build_text, axis=1)

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self.embedding_matrix = None
        self.index = None
        self.product_ids: list[int] = []

        if not self.products_df.empty:
            tfidf = self.vectorizer.fit_transform(self.products_df["search_text"].tolist())
            dense = tfidf.astype(np.float32).toarray()
            faiss.normalize_L2(dense)
            self.embedding_matrix = dense
            self.index = faiss.IndexFlatIP(dense.shape[1])
            self.index.add(dense)
            self.product_ids = self.products_df["id"].astype(int).tolist()

    def _build_text(self, row: pd.Series) -> str:
        parts = [
            str(row.get("name", "")),
            str(row.get("category_name", "")),
            str(row.get("book_author", "")),
            str(row.get("book_publisher", "")),
            str(row.get("electronics_brand", "")),
            str(row.get("electronics_warranty", "")),
            str(row.get("fashion_color", "")),
            str(row.get("fashion_size", "")),
        ]
        return " ".join(part for part in parts if part).lower()

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        if not query or self.index is None:
            return []
        query_vec = self.vectorizer.transform([query]).astype(np.float32).toarray()
        faiss.normalize_L2(query_vec)
        scores, indices = self.index.search(query_vec, top_k)
        result: list[tuple[int, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            result.append((self.product_ids[int(idx)], float(score)))
        return result
