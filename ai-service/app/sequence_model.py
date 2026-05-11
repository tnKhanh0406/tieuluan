from __future__ import annotations

from collections import defaultdict

import pandas as pd


class SequenceModel:
    """Train a next-item transition model from user behavior sequences."""

    def __init__(self, behavior_df: pd.DataFrame):
        self.behavior_df = behavior_df.copy()
        self.transition_counts: dict[int, dict[int, float]] = defaultdict(dict)
        self.transition_probs: dict[int, dict[int, float]] = defaultdict(dict)
        self.trained = False
        self.training_rows = 0

    def train(self) -> None:
        if self.behavior_df.empty:
            self.trained = True
            self.training_rows = 0
            return

        ordered = self.behavior_df.sort_values(["user_id", "timestamp", "product_id"]).copy()
        self.training_rows = int(len(ordered))

        for _, group in ordered.groupby("user_id"):
            items = group["product_id"].astype(int).tolist()
            for src, dst in zip(items, items[1:]):
                self.transition_counts[src][dst] = self.transition_counts[src].get(dst, 0.0) + 1.0

        for src, dst_map in self.transition_counts.items():
            total = sum(dst_map.values()) or 1.0
            self.transition_probs[src] = {dst: count / total for dst, count in dst_map.items()}

        self.trained = True

    def predict_scores(self, history: list[int], top_k: int = 20) -> dict[int, float]:
        if not history:
            return {}

        recent = history[-5:]
        weighted: dict[int, float] = defaultdict(float)
        for offset, src in enumerate(reversed(recent), start=1):
            decay = 1.0 / offset
            for dst, prob in self.transition_probs.get(int(src), {}).items():
                weighted[dst] += prob * decay

        ranked = sorted(weighted.items(), key=lambda item: item[1], reverse=True)
        return {int(pid): float(score) for pid, score in ranked[:top_k]}
