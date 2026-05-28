"""Idempotent seed for the demo schema. Run once, before the workload."""

from __future__ import annotations

import argparse
import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.database import engine

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

USERS = 5_000
PRODUCTS = 500
ORDERS = 50_000
ORDER_ITEMS = 150_000
EVENTS = 200_000
VECTOR_ITEMS = 10_000

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS demo;

CREATE TABLE IF NOT EXISTS demo.users (
    id           BIGSERIAL PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    country      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo.products (
    id           BIGSERIAL PRIMARY KEY,
    sku          TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    price_cents  INTEGER NOT NULL,
    category     TEXT
);

CREATE TABLE IF NOT EXISTS demo.orders (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES demo.users(id),
    status        TEXT NOT NULL,
    total_cents   INTEGER NOT NULL,
    shipping_zip  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo.order_items (
    id               BIGSERIAL PRIMARY KEY,
    order_id         BIGINT NOT NULL REFERENCES demo.orders(id),
    product_id       BIGINT NOT NULL REFERENCES demo.products(id),
    qty              INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS demo.events (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES demo.users(id),
    event_type   TEXT NOT NULL,
    payload      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo.vector_items (
    id           BIGSERIAL PRIMARY KEY,
    category     TEXT NOT NULL,
    embedding    vector(8) NOT NULL
);

CREATE INDEX IF NOT EXISTS orders_user_id_idx ON demo.orders(user_id);
CREATE INDEX IF NOT EXISTS order_items_order_id_idx ON demo.order_items(order_id);
CREATE INDEX IF NOT EXISTS events_user_created_idx ON demo.events(user_id, created_at);
CREATE INDEX IF NOT EXISTS vector_items_embedding_hnsw_idx ON demo.vector_items USING hnsw (embedding vector_l2_ops);
"""

TRUNCATE = """
TRUNCATE demo.events, demo.order_items, demo.orders, demo.products, demo.users RESTART IDENTITY CASCADE;
TRUNCATE demo.vector_items RESTART IDENTITY CASCADE;
"""

COUNTRIES = ["US", "GB", "DE", "FR", "JP", "IN", "BR", "AU", "CA", "MX"]
STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]
ZIPS = ["10001", "94103", "60601", "75001", "98101", "30301", "02101", "85001"]
EVENTS_T = ["page_view", "click", "purchase", "signup", "logout"]
CATEGORIES = ["electronics", "clothing", "food", "books", "home", "sports"]


def _ensure_schema(conn) -> None:
    conn.execute(text(DDL))


def _row_count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT count(*) FROM demo.{table}")).scalar_one()


def seed(reset: bool = False) -> None:
    rng = random.Random(42)
    now = datetime.now(UTC)

    with engine.begin() as conn:
        _ensure_schema(conn)
        if reset:
            log.info("truncating demo tables")
            conn.execute(text(TRUNCATE))

        if _row_count(conn, "users") < USERS:
            log.info("seeding %s users", USERS)
            rows = [
                {
                    "email": f"user{i}@example.com",
                    "country": rng.choice(COUNTRIES),
                    "created_at": now - timedelta(days=rng.randint(0, 730)),
                }
                for i in range(USERS)
            ]
            conn.execute(
                text("INSERT INTO demo.users (email, country, created_at) VALUES (:email, :country, :created_at)"),
                rows,
            )

        if _row_count(conn, "products") < PRODUCTS:
            log.info("seeding %s products", PRODUCTS)
            rows = [
                {
                    "sku": f"SKU-{i:05d}",
                    "name": f"Product {i}",
                    "price_cents": rng.randint(99, 99999),
                    "category": rng.choice(CATEGORIES),
                }
                for i in range(PRODUCTS)
            ]
            conn.execute(
                text("INSERT INTO demo.products (sku, name, price_cents, category) VALUES (:sku, :name, :price_cents, :category)"),
                rows,
            )

        if _row_count(conn, "orders") < ORDERS:
            log.info("seeding %s orders", ORDERS)
            rows = []
            for _ in range(ORDERS):
                rows.append(
                    {
                        "user_id": rng.randint(1, USERS),
                        "status": rng.choice(STATUSES),
                        "total_cents": rng.randint(500, 500_000),
                        "shipping_zip": rng.choice(ZIPS),
                        "created_at": now - timedelta(days=rng.randint(0, 365)),
                    }
                )
                if len(rows) >= 5_000:
                    conn.execute(
                        text(
                            "INSERT INTO demo.orders (user_id, status, total_cents, shipping_zip, created_at) "
                            "VALUES (:user_id, :status, :total_cents, :shipping_zip, :created_at)"
                        ),
                        rows,
                    )
                    rows = []
            if rows:
                conn.execute(
                    text(
                        "INSERT INTO demo.orders (user_id, status, total_cents, shipping_zip, created_at) "
                        "VALUES (:user_id, :status, :total_cents, :shipping_zip, :created_at)"
                    ),
                    rows,
                )

        if _row_count(conn, "order_items") < ORDER_ITEMS:
            log.info("seeding %s order_items", ORDER_ITEMS)
            rows = []
            for _ in range(ORDER_ITEMS):
                rows.append(
                    {
                        "order_id": rng.randint(1, ORDERS),
                        "product_id": rng.randint(1, PRODUCTS),
                        "qty": rng.randint(1, 5),
                        "unit_price_cents": rng.randint(99, 99999),
                    }
                )
                if len(rows) >= 10_000:
                    conn.execute(
                        text(
                            "INSERT INTO demo.order_items (order_id, product_id, qty, unit_price_cents) "
                            "VALUES (:order_id, :product_id, :qty, :unit_price_cents)"
                        ),
                        rows,
                    )
                    rows = []
            if rows:
                conn.execute(
                    text(
                        "INSERT INTO demo.order_items (order_id, product_id, qty, unit_price_cents) "
                        "VALUES (:order_id, :product_id, :qty, :unit_price_cents)"
                    ),
                    rows,
                )

        if _row_count(conn, "events") < EVENTS:
            log.info("seeding %s events", EVENTS)
            _event_sql = text(
                "INSERT INTO demo.events (user_id, event_type, payload, created_at) "
                "VALUES (:user_id, :event_type, CAST(:payload AS jsonb), :created_at)"
            )
            rows = []
            for _ in range(EVENTS):
                rows.append(
                    {
                        "user_id": rng.randint(1, USERS),
                        "event_type": rng.choice(EVENTS_T),
                        "payload": '{"v":1}',
                        "created_at": now - timedelta(minutes=rng.randint(0, 60 * 24 * 90)),
                    }
                )
                if len(rows) >= 10_000:
                    conn.execute(_event_sql, rows)
                    rows = []
            if rows:
                conn.execute(_event_sql, rows)

        if _row_count(conn, "vector_items") < VECTOR_ITEMS:
            log.info("seeding %s vector_items", VECTOR_ITEMS)
            rows = []
            for _ in range(VECTOR_ITEMS):
                vec = [round(rng.uniform(-1, 1), 4) for _ in range(8)]
                rows.append(
                    {
                        "category": rng.choice(CATEGORIES),
                        "embedding": "[" + ",".join(str(v) for v in vec) + "]",
                    }
                )
                if len(rows) >= 2_000:
                    conn.execute(
                        text(
                            "INSERT INTO demo.vector_items (category, embedding) "
                            "VALUES (:category, CAST(:embedding AS vector))"
                        ),
                        rows,
                    )
                    rows = []
            if rows:
                conn.execute(
                    text(
                        "INSERT INTO demo.vector_items (category, embedding) "
                        "VALUES (:category, CAST(:embedding AS vector))"
                    ),
                    rows,
                )

        conn.execute(text("ANALYZE demo.users, demo.products, demo.orders, demo.order_items, demo.events, demo.vector_items"))
    log.info("seed done")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="truncate before seeding")
    args = p.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
