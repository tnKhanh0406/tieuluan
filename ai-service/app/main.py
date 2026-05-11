from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Optional

import matplotlib
import pandas as pd
import networkx as nx
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .recommender import HybridRecommender
from .schemas import ChatRequest, ChatResponse, RecommendationItem, RecommendationResponse, TrackEventRequest

app = FastAPI(title="Ecommerce AI Service", version="1.0.0")

BEHAVIOR_CSV = Path(os.getenv("BEHAVIOR_CSV", "/app/data/user_behavior.csv"))
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8000")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpass")

engine: Optional[HybridRecommender] = None
behavior_cache: Optional[pd.DataFrame] = None
products_cache: Optional[pd.DataFrame] = None

action_aliases = {
    "add_to_cart": "add_to_cart",
    "add-to-cart": "add_to_cart",
    "cart": "add_to_cart",
    "purchase": "purchase",
    "buy": "purchase",
}


def load_behavior_data() -> pd.DataFrame:
    if not BEHAVIOR_CSV.exists():
        return pd.DataFrame(columns=["user_id", "product_id", "action", "timestamp"])
    df = pd.read_csv(BEHAVIOR_CSV)
    df = df.rename(columns={"time": "timestamp"})
    if "timestamp" not in df.columns:
        df["timestamp"] = range(len(df))
    df["action"] = df["action"].astype(str).str.lower().replace(action_aliases)
    df["user_id"] = df["user_id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)
    df["timestamp"] = df["timestamp"].astype(int)
    return df


def load_products() -> pd.DataFrame:
    response = requests.get(f"{PRODUCT_SERVICE_URL}/products/", timeout=20)
    response.raise_for_status()
    products = response.json()
    rows = []
    for product in products:
        rows.append(
            {
                "id": product.get("id"),
                "name": product.get("name", ""),
                "price": product.get("price", 0.0),
                "stock": product.get("stock", 0),
                "category_name": product.get("category_name", ""),
                "book_author": (product.get("book") or {}).get("author", ""),
                "book_publisher": (product.get("book") or {}).get("publisher", ""),
                "electronics_brand": (product.get("electronics") or {}).get("brand", ""),
                "electronics_warranty": (product.get("electronics") or {}).get("warranty", ""),
                "fashion_color": (product.get("fashion") or {}).get("color", ""),
                "fashion_size": (product.get("fashion") or {}).get("size", ""),
            }
        )
    return pd.DataFrame(rows)


def load_products_with_retry(retries: int = 10, delay_seconds: float = 2.0) -> pd.DataFrame:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            return load_products()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_seconds)

    if last_error is not None:
        print(f"[ai-service] Failed to load products from product-service: {last_error}")
    return pd.DataFrame()


def collect_graph_snapshot(max_edges: int, min_score: float) -> tuple[dict[int, dict[str, str]], list[tuple[int, int, float]]]:
    if engine is None:
        return {}, []

    product_meta: dict[int, dict[str, str]] = {}
    for row in engine.products_df.fillna("").itertuples(index=False):
        product_meta[int(row.id)] = {
            "name": str(getattr(row, "name", "")),
            "category": str(getattr(row, "category_name", "unknown")) or "unknown",
        }

    edges: list[tuple[int, int, float]] = []
    if engine.graph_store.driver is not None:
        try:
            with engine.graph_store.driver.session() as session:
                result = session.run(
                    "MATCH (a:Product)-[s:SIMILAR]->(b:Product) "
                    "WHERE s.score >= $min_score "
                    "RETURN a.id AS src, b.id AS dst, s.score AS score "
                    "ORDER BY s.score DESC LIMIT $limit",
                    min_score=float(min_score),
                    limit=int(max_edges),
                )
                for row in result:
                    edges.append((int(row["src"]), int(row["dst"]), float(row["score"])))
        except Exception:
            edges = []

    if not edges:
        for src, targets in engine.graph_store.similar_map.items():
            for dst, score in targets.items():
                if float(score) >= float(min_score):
                    edges.append((int(src), int(dst), float(score)))
        edges.sort(key=lambda item: item[2], reverse=True)
        edges = edges[: int(max_edges)]

    return product_meta, edges


def build_graph_png(max_nodes: int, max_edges: int, min_score: float) -> bytes:
    product_meta, edges = collect_graph_snapshot(max_edges=max_edges, min_score=min_score)
    if not edges:
        raise HTTPException(status_code=404, detail="No graph edges available for visualization.")

    graph = nx.DiGraph()
    for src, dst, score in edges:
        graph.add_edge(src, dst, weight=score)

    # Keep highest-degree nodes first for readability.
    if graph.number_of_nodes() > max_nodes:
        degrees = sorted(graph.degree, key=lambda item: item[1], reverse=True)
        keep_nodes = {node for node, _ in degrees[:max_nodes]}
        graph = graph.subgraph(keep_nodes).copy()

    category_palette: dict[str, tuple[float, float, float, float]] = {}
    cmap = plt.get_cmap("tab20")
    color_cursor = 0
    node_colors = []
    for node_id in graph.nodes:
        category = product_meta.get(int(node_id), {}).get("category", "unknown")
        if category not in category_palette:
            category_palette[category] = cmap(color_cursor % 20)
            color_cursor += 1
        node_colors.append(category_palette[category])

    pos = nx.spring_layout(graph, seed=42, k=0.75)
    fig = plt.figure(figsize=(13, 9), dpi=150)
    nx.draw_networkx_edges(
        graph,
        pos,
        alpha=0.3,
        arrows=True,
        arrowsize=10,
        width=[max(0.5, graph[u][v]["weight"] * 2.0) for u, v in graph.edges],
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        node_color=node_colors,
        node_size=420,
        linewidths=0.6,
        edgecolors="white",
    )

    labels = {}
    degree_rank = sorted(graph.degree, key=lambda item: item[1], reverse=True)
    for node_id, _ in degree_rank[: min(24, len(degree_rank))]:
        labels[node_id] = product_meta.get(int(node_id), {}).get("name", str(node_id))
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=7)

    plt.title("Knowledge Graph (Product Similarity)")
    plt.axis("off")
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


@app.on_event("startup")
def startup_event() -> None:
    global engine, behavior_cache, products_cache
    behavior_cache = load_behavior_data()
    products_cache = load_products_with_retry()
    engine = HybridRecommender(
        behavior_cache,
        products_cache,
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
    )
    app.state.engine = engine


@app.get("/ai/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "behavior_file": str(BEHAVIOR_CSV),
        "behavior_rows": 0 if behavior_cache is None else int(len(behavior_cache)),
        "product_rows": 0 if products_cache is None else int(len(products_cache)),
    }


@app.get("/ai/summary")
def summary() -> dict[str, object]:
    if engine is None:
        raise HTTPException(status_code=503, detail="AI engine has not started yet.")
    return engine.summary()


@app.get("/ai/recommend", response_model=RecommendationResponse)
def recommend(
    user_id: int = Query(..., ge=1),
    limit: int = Query(5, ge=1, le=20),
    query: Optional[str] = Query(default=None),
) -> RecommendationResponse:
    if engine is None:
        raise HTTPException(status_code=503, detail="AI engine has not started yet.")
    recommendations, strategy, intent = engine.recommend(user_id=user_id, limit=limit, query=query)
    summary_text = (
        f"Da phan tich {len(recommendations)} san pham cho user {user_id}. "
        f"Strategy: behavior={strategy['behavior']}, sequence={strategy['sequence']}, graph={strategy['graph']}, semantic={strategy['semantic']}."
    )
    return RecommendationResponse(
        user_id=user_id,
        limit=limit,
        query=query,
        intent=intent,
        recommendations=[RecommendationItem(**item.__dict__) for item in recommendations],
        strategy=strategy,
        summary=summary_text,
    )


@app.post("/ai/chatbot", response_model=ChatResponse)
def chatbot(payload: ChatRequest) -> ChatResponse:
    if engine is None:
        raise HTTPException(status_code=503, detail="AI engine has not started yet.")
    answer, recommendations, intent = engine.chat(payload.query, user_id=payload.user_id, limit=payload.limit)
    return ChatResponse(
        intent=intent,
        answer=answer,
        recommendations=[RecommendationItem(**item.__dict__) for item in recommendations],
    )


@app.post("/ai/track")
def track_event(payload: TrackEventRequest) -> dict[str, object]:
    global engine, behavior_cache

    if engine is None or behavior_cache is None:
        raise HTTPException(status_code=503, detail="AI engine has not started yet.")

    new_row = pd.DataFrame(
        [{
            "user_id": int(payload.user_id),
            "product_id": int(payload.product_id),
            "action": payload.action,
            "timestamp": int(payload.timestamp),
        }]
    )
    updated = pd.concat([behavior_cache, new_row], ignore_index=True)
    behavior_cache = updated
    engine = HybridRecommender(
        updated,
        products_cache if products_cache is not None else pd.DataFrame(),
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
    )
    app.state.engine = engine
    return {"detail": "event recorded", "rows": int(len(updated))}


@app.get("/ai/graph/visualize")
def visualize_graph(
    max_nodes: int = Query(40, ge=5, le=200),
    max_edges: int = Query(120, ge=10, le=1000),
    min_score: float = Query(0.05, ge=0.0, le=1.0),
) -> StreamingResponse:
    if engine is None:
        raise HTTPException(status_code=503, detail="AI engine has not started yet.")
    png_bytes = build_graph_png(max_nodes=max_nodes, max_edges=max_edges, min_score=min_score)
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")
