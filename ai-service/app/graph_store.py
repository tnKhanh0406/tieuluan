from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Optional

import pandas as pd

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None


class GraphStore:
    def __init__(self, behavior_df: pd.DataFrame, neo4j_uri: Optional[str] = None, neo4j_user: str = "neo4j", neo4j_password: str = "neo4jpass"):
        self.behavior_df = behavior_df
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        self.similar_map = self._build_similarity_map(behavior_df)

        if neo4j_uri and GraphDatabase is not None:
            try:
                self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            except Exception:
                self.driver = None

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def _build_similarity_map(self, behavior_df: pd.DataFrame) -> dict[int, dict[int, float]]:
        by_user = defaultdict(list)
        for row in behavior_df.itertuples(index=False):
            by_user[int(row.user_id)].append(int(row.product_id))

        co_count: dict[int, dict[int, float]] = defaultdict(dict)
        freq: dict[int, float] = defaultdict(float)

        for products in by_user.values():
            unique = list(dict.fromkeys(products))
            for pid in unique:
                freq[pid] += 1.0
            for left, right in combinations(unique, 2):
                co_count[left][right] = co_count[left].get(right, 0.0) + 1.0
                co_count[right][left] = co_count[right].get(left, 0.0) + 1.0

        sim: dict[int, dict[int, float]] = defaultdict(dict)
        for left, right_map in co_count.items():
            for right, count in right_map.items():
                sim[left][right] = count / ((freq[left] * freq[right]) ** 0.5)
        return sim

    def ingest_to_neo4j(self, products_df: pd.DataFrame) -> bool:
        if self.driver is None:
            return False

        product_rows = products_df[["id", "name", "category_name", "price"]].fillna("").to_dict(orient="records")
        user_rows = self.behavior_df[["user_id"]].drop_duplicates().to_dict(orient="records")
        event_rows = self.behavior_df[["user_id", "product_id", "action", "timestamp"]].to_dict(orient="records")

        try:
            with self.driver.session() as session:
                session.run(
                    "UNWIND $rows AS r \n"
                    "MERGE (p:Product {id: toInteger(r.id)}) \n"
                    "SET p.name = r.name, p.category = r.category_name, p.price = toFloat(r.price)",
                    rows=product_rows,
                )
                session.run("UNWIND $rows AS r MERGE (:User {id: toInteger(r.user_id)})", rows=user_rows)
                session.run(
                    "UNWIND $rows AS r \n"
                    "MATCH (u:User {id: toInteger(r.user_id)}) \n"
                    "MATCH (p:Product {id: toInteger(r.product_id)}) \n"
                    "MERGE (u)-[e:INTERACT {action: r.action}]->(p) \n"
                    "SET e.timestamp = toInteger(r.timestamp)",
                    rows=event_rows,
                )

                similar_rows = []
                for src, targets in self.similar_map.items():
                    for dst, score in targets.items():
                        if score > 0:
                            similar_rows.append({"src": src, "dst": dst, "score": float(score)})

                session.run(
                    "UNWIND $rows AS r \n"
                    "MATCH (a:Product {id: toInteger(r.src)}) \n"
                    "MATCH (b:Product {id: toInteger(r.dst)}) \n"
                    "MERGE (a)-[s:SIMILAR]->(b) \n"
                    "SET s.score = toFloat(r.score)",
                    rows=similar_rows,
                )
            return True
        except Exception:
            return False

    def similar_products(self, product_id: int, top_k: int = 10) -> list[tuple[int, float]]:
        if self.driver is not None:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        "MATCH (:Product {id: $pid})-[s:SIMILAR]->(rec:Product) \n"
                        "RETURN rec.id AS product_id, s.score AS score \n"
                        "ORDER BY s.score DESC LIMIT $k",
                        pid=int(product_id),
                        k=int(top_k),
                    )
                    rows = [(int(r["product_id"]), float(r["score"])) for r in result]
                    if rows:
                        return rows
            except Exception:
                pass

        fallback = self.similar_map.get(int(product_id), {})
        ranked = sorted(fallback.items(), key=lambda item: item[1], reverse=True)
        return [(int(pid), float(score)) for pid, score in ranked[:top_k]]
