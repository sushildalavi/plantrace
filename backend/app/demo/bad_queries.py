"""Named SQL templates the workload script picks from.

A mix of realistic-shaped read queries: indexed lookups, missing-index scans,
unindexed sorts, prefix-wildcard LIKE, full-table aggregates, JOINs, group-by
analytics, CTE rollups, and a deliberately ugly N+1 scan.

Halfway through the workload run, ``orders.user_id`` is dropped to manufacture
an ``index_scan_to_seq_scan`` regression on ``good_user_orders``.
"""

from __future__ import annotations

QUERIES: dict[str, str] = {
    "good_user_orders": (
        "SELECT * FROM demo.orders WHERE user_id = {user_id} LIMIT 50"
    ),
    "missing_index": (
        "SELECT * FROM demo.orders WHERE shipping_zip = '{zip}'"
    ),
    "unindexed_order_by": (
        "SELECT id, total_cents FROM demo.orders ORDER BY total_cents DESC LIMIT 10"
    ),
    "like_prefix_wildcard": (
        "SELECT id, email FROM demo.users WHERE email LIKE '%{domain}'"
    ),
    "sequential_scan": (
        "SELECT count(*) FROM demo.events WHERE event_type = '{evt}'"
    ),
    "large_join": (
        "SELECT u.email, count(*) AS c FROM demo.users u "
        "JOIN demo.orders o ON o.user_id = u.id "
        "JOIN demo.order_items oi ON oi.order_id = o.id "
        "WHERE o.created_at > now() - interval '30 days' "
        "GROUP BY u.email ORDER BY c DESC LIMIT 20"
    ),
    "country_revenue": (
        "SELECT u.country, sum(o.total_cents) AS rev "
        "FROM demo.users u JOIN demo.orders o ON o.user_id = u.id "
        "WHERE o.status IN ('paid', 'shipped', 'delivered') "
        "GROUP BY u.country ORDER BY rev DESC LIMIT 25"
    ),
    "events_recent": (
        "SELECT user_id, count(*) FROM demo.events "
        "WHERE created_at > now() - interval '7 days' "
        "GROUP BY user_id ORDER BY count(*) DESC LIMIT 50"
    ),
    "top_products": (
        "SELECT p.sku, p.name, sum(oi.qty) AS units "
        "FROM demo.products p JOIN demo.order_items oi ON oi.product_id = p.id "
        "GROUP BY p.id ORDER BY units DESC LIMIT 30"
    ),
    "category_breakdown": (
        "SELECT p.category, count(distinct o.id) AS orders, "
        "sum(oi.qty * oi.unit_price_cents) AS revenue "
        "FROM demo.products p "
        "JOIN demo.order_items oi ON oi.product_id = p.id "
        "JOIN demo.orders o ON o.id = oi.order_id "
        "GROUP BY p.category ORDER BY revenue DESC"
    ),
    "stale_event_lookup": (
        "SELECT * FROM demo.events WHERE payload->>'v' = '{evt_v}' LIMIT 25"
    ),
    "user_profile": (
        "SELECT u.id, u.email, u.country, "
        "(SELECT count(*) FROM demo.orders o WHERE o.user_id = u.id) AS orders_n "
        "FROM demo.users u WHERE u.id = {user_id}"
    ),
    "order_status_funnel": (
        "SELECT status, count(*) FROM demo.orders GROUP BY status ORDER BY count(*) DESC"
    ),
    "product_search": (
        "SELECT id, sku, name FROM demo.products WHERE name ILIKE '%{name_like}%' LIMIT 20"
    ),
    "active_users_30d": (
        "WITH active AS ("
        " SELECT DISTINCT user_id FROM demo.events "
        " WHERE created_at > now() - interval '30 days'"
        ") "
        "SELECT count(*) FROM active"
    ),
    "vector_similarity": (
        "SELECT id, category FROM demo.vector_items "
        "ORDER BY embedding <-> CAST('[0.11,0.22,0.33,0.44,0.55,0.66,0.77,0.88]' AS vector) "
        "LIMIT 10"
    ),
}

WEIGHTS: dict[str, int] = {
    "good_user_orders": 8,
    "missing_index": 3,
    "unindexed_order_by": 2,
    "like_prefix_wildcard": 2,
    "sequential_scan": 4,
    "large_join": 1,
    "country_revenue": 2,
    "events_recent": 2,
    "top_products": 2,
    "category_breakdown": 1,
    "stale_event_lookup": 2,
    "user_profile": 4,
    "order_status_funnel": 3,
    "product_search": 2,
    "active_users_30d": 1,
    "vector_similarity": 3,
}

ZIP_CODES = ["10001", "94103", "60601", "75001", "98101", "30301"]
DOMAINS = ["@gmail.com", "@yahoo.com", "@outlook.com", "@example.com"]
EVENT_TYPES = ["page_view", "click", "purchase", "signup", "logout"]
NAME_LIKES = ["product", "1", "2", "3", "5"]
EVT_VALUES = ["1", "2"]
