import random
import csv

# Các flow hành vi (giống user thật)
actions_flow = [
    ["view", "click", "add_to_cart", "purchase"],
    ["view", "click"],
    ["view", "wishlist"],
    ["view", "compare"],
    ["search", "view", "click"]
]

# Map category -> product range
category_products = {
    4: list(range(11, 21)),
    3: list(range(21, 31)),
    2: list(range(31, 41)),
    6: list(range(1, 11)),
    5: list(range(51, 61)),
    7: list(range(61, 71)),
    8: list(range(41, 51)),
    9: list(range(71, 81)),
    10: list(range(81, 91)),
    1: list(range(91, 101))
}

# ✅ User ID từ 3 → 32
user_ids = list(range(3, 33))

categories = list(category_products.keys())

# Tạo sở thích user
user_preferences = {
    user_id: random.sample(categories, k=2)
    for user_id in user_ids
}

data = []
timestamp = 1

while len(data) < 1500:
    user_id = random.choice(user_ids)
    flow = random.choice(actions_flow)

    preferred_categories = user_preferences[user_id]
    category = random.choice(preferred_categories)

    for action in flow:
        if len(data) >= 1500:
            break

        product_id = random.choice(category_products[category])

        data.append([user_id, product_id, action, timestamp])
        timestamp += 1

# shuffle nhẹ
random.shuffle(data)

# ghi CSV
with open("user_behavior.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["user_id", "product_id", "action", "timestamp"])
    writer.writerows(data)

print("Generated 1500 user behavior records (user_id 3→32)!")