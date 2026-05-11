from __future__ import annotations

from typing import Optional, Any


class RAGEngine:
    def generate_answer(
        self,
        query: str,
        intent: str,
        retrieved: list[Any],
        user_id: Optional[int],
    ) -> str:
        if not retrieved:
            return (
                f"Minh chua tim thay san pham phu hop voi truy van '{query}'. "
                "Ban hay thu mo ta ro hon, vi du: refrigerator gia tot duoi 15 trieu."
            )

        top = retrieved[0]
        lines = [
            f"Truy van: {query}",
            f"Intent: {intent}",
            f"Goi y tot nhat: #{top.product_id} {top.name} ({top.category}) gia {top.price}",
        ]

        if len(retrieved) > 1:
            alt = ", ".join([f"#{item.product_id} {item.name}" for item in retrieved[1:4]])
            lines.append(f"Lua chon thay the: {alt}")

        if user_id is not None:
            lines.append(f"Duoc ca nhan hoa theo hanh vi cua user {user_id}.")

        return " ".join(lines)
