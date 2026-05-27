"""Run a randomized workload against the demo schema.

Halfway through the loop, drops ``orders.user_id`` index so the next collector
run records an ``index_scan_to_seq_scan`` regression on ``good_user_orders``.
"""

from __future__ import annotations

import argparse
import logging
import random

from sqlalchemy import text

from app.database import engine
from app.demo.bad_queries import (
    DOMAINS,
    EVENT_TYPES,
    EVT_VALUES,
    NAME_LIKES,
    QUERIES,
    WEIGHTS,
    ZIP_CODES,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _params(rng: random.Random) -> dict[str, str | int]:
    return {
        "user_id": rng.randint(1, 5_000),
        "zip": rng.choice(ZIP_CODES),
        "domain": rng.choice(DOMAINS),
        "evt": rng.choice(EVENT_TYPES),
        "evt_v": rng.choice(EVT_VALUES),
        "name_like": rng.choice(NAME_LIKES),
    }


def _pick(rng: random.Random) -> str:
    pool: list[str] = []
    for name, w in WEIGHTS.items():
        pool.extend([name] * w)
    return rng.choice(pool)


def run(iterations: int, drop_index: bool, restore_index: bool, seed: int = 0) -> None:
    rng = random.Random(seed) if seed else random.Random()
    drop_at = iterations // 2 if drop_index else None
    log.info(
        "running %s iterations (drop_index=%s, restore=%s)",
        iterations,
        drop_index,
        restore_index,
    )

    with engine.connect() as conn:
        for i in range(iterations):
            if drop_at is not None and i == drop_at:
                log.warning("dropping demo.orders_user_id_idx (regression incoming)")
                with conn.begin():
                    conn.execute(text("DROP INDEX IF EXISTS demo.orders_user_id_idx"))
                    conn.execute(text("DROP INDEX IF EXISTS demo.vector_items_embedding_hnsw_idx"))

            name = _pick(rng)
            sql = QUERIES[name].format(**_params(rng))
            try:
                with conn.begin():
                    conn.execute(text(sql))
            except Exception as e:
                log.warning("query %s failed: %s", name, e)

        if restore_index:
            log.info("recreating demo.orders_user_id_idx")
            with conn.begin():
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS orders_user_id_idx ON demo.orders(user_id)"
                    )
                )

    log.info("workload done")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument(
        "--drop-index",
        action="store_true",
        default=True,
        help="drop orders.user_id midway",
    )
    p.add_argument("--no-drop-index", dest="drop_index", action="store_false")
    p.add_argument(
        "--restore-index",
        action="store_true",
        help="recreate the index after the run",
    )
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    run(args.iterations, args.drop_index, args.restore_index, seed=args.seed)


if __name__ == "__main__":
    main()
