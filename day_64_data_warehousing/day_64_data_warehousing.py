#!/usr/bin/env python3
"""
Data Warehousing: an executable ETL and analytical reporting demonstration.

The source database represents an operational change log. The warehouse uses
a dimensional model with customer, product and date dimensions and a sales fact
table. Incremental extraction, validation, quarantine, transactional loading,
idempotency and OLAP aggregation are demonstrated using SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any


MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807


@dataclass(frozen=True)
class ETLStats:
    extracted: int = 0
    loaded_or_updated: int = 0
    unchanged: int = 0
    quarantined: int = 0
    skipped: int = 0


class DataQualityError(ValueError):
    """Raised when a source record violates an ETL quality rule."""


class OperationalSource:
    """Small operational store with an append-only change sequence."""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self._seed_data()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE customers (
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                region TEXT NOT NULL
            );

            CREATE TABLE products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL
            );

            -- This table represents a CDC feed. Each correction creates a
            -- new sequence number rather than overwriting the previous event.
            CREATE TABLE sales_changes (
                change_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                source_sale_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                sale_date TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price_cents INTEGER NOT NULL,
                status TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
            """
        )

    def _seed_data(self) -> None:
        self.connection.executemany(
            """
            INSERT INTO customers(customer_id, customer_name, region)
            VALUES (?, ?, ?)
            """,
            [
                ("C001", "Asha Mehta", "North"),
                ("C002", "Rohan Singh", "South"),
                ("C003", "Mira Das", "West"),
            ],
        )

        self.connection.executemany(
            """
            INSERT INTO products(product_id, product_name, category)
            VALUES (?, ?, ?)
            """,
            [
                ("P100", "Laptop", "Electronics"),
                ("P200", "Monitor", "Electronics"),
                ("P300", "Office Chair", "Furniture"),
            ],
        )

        self.connection.executemany(
            """
            INSERT INTO sales_changes(
                source_sale_id, customer_id, product_id, sale_date,
                quantity, unit_price_cents, status, changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "S1001", "C001", "P100", "2026-10-01",
                    2, 75000, "COMPLETED", "2026-10-01T10:00:00",
                ),
                (
                    "S1002", "C002", "P200", "2026-10-02",
                    1, 22000, "COMPLETED", "2026-10-02T11:00:00",
                ),
                (
                    "S1003", "C003", "P300", "2026-10-03",
                    3, 12000, "COMPLETED", "2026-10-03T12:00:00",
                ),
                (
                    "S1004", "C001", "P200", "2026-10-04",
                    -1, 22000, "COMPLETED", "2026-10-04T12:00:00",
                ),
                (
                    "S1005", "C002", "P100", "2026-10-05",
                    1, 75000, "CANCELLED", "2026-10-05T14:00:00",
                ),
            ],
        )

        self.connection.commit()

    def extract_after(self, last_change_seq: int) -> list[sqlite3.Row]:
        """Extract only CDC events that have not reached the warehouse."""
        cursor = self.connection.execute(
            """
            SELECT
                change_seq,
                source_sale_id,
                customer_id,
                product_id,
                sale_date,
                quantity,
                unit_price_cents,
                status,
                changed_at
            FROM sales_changes
            WHERE change_seq > ?
            ORDER BY change_seq
            """,
            (last_change_seq,),
        )
        return cursor.fetchall()

    def add_change(
        self,
        source_sale_id: str,
        customer_id: str,
        product_id: str,
        sale_date: str,
        quantity: int,
        unit_price_cents: int,
        status: str,
        changed_at: str,
    ) -> int:
        """Append a new source event, including corrections to earlier sales."""
        cursor = self.connection.execute(
            """
            INSERT INTO sales_changes(
                source_sale_id, customer_id, product_id, sale_date,
                quantity, unit_price_cents, status, changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_sale_id,
                customer_id,
                product_id,
                sale_date,
                quantity,
                unit_price_cents,
                status,
                changed_at,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def customer_rows(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM customers ORDER BY customer_id"
        ).fetchall()

    def product_rows(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM products ORDER BY product_id"
        ).fetchall()


class AnalyticalWarehouse:
    """Dimensional warehouse with an idempotent fact-loading strategy."""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                region TEXT NOT NULL
            );

            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL
            );

            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT NOT NULL UNIQUE,
                year_number INTEGER NOT NULL,
                quarter_number INTEGER NOT NULL,
                month_number INTEGER NOT NULL,
                day_number INTEGER NOT NULL
            );

            CREATE TABLE fact_sales (
                source_sale_id TEXT PRIMARY KEY,
                source_change_seq INTEGER NOT NULL,
                date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
                customer_key INTEGER NOT NULL
                    REFERENCES dim_customer(customer_key),
                product_key INTEGER NOT NULL
                    REFERENCES dim_product(product_key),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price_cents INTEGER NOT NULL
                    CHECK (unit_price_cents >= 0),
                gross_cents INTEGER NOT NULL CHECK (gross_cents >= 0),
                source_changed_at TEXT NOT NULL
            );

            CREATE INDEX idx_fact_sales_date
                ON fact_sales(date_key);

            CREATE INDEX idx_fact_sales_customer_date
                ON fact_sales(customer_key, date_key);

            CREATE INDEX idx_fact_sales_product_date
                ON fact_sales(product_key, date_key);

            CREATE TABLE etl_state (
                state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
                last_change_seq INTEGER NOT NULL DEFAULT 0,
                last_successful_load TEXT
            );

            INSERT INTO etl_state(state_id, last_change_seq)
            VALUES (1, 0);

            CREATE TABLE etl_quarantine (
                change_seq INTEGER PRIMARY KEY,
                source_sale_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                original_record TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _validate_record(row: sqlite3.Row) -> None:
        if not row["source_sale_id"]:
            raise DataQualityError("Missing source sale identifier")

        if row["quantity"] <= 0:
            raise DataQualityError("Quantity must be greater than zero")

        if row["unit_price_cents"] < 0:
            raise DataQualityError("Unit price cannot be negative")

        if row["quantity"] and (
            row["unit_price_cents"] >
            MAX_SQLITE_INTEGER // row["quantity"]
        ):
            raise DataQualityError("Gross amount exceeds SQLite integer range")

        try:
            date.fromisoformat(row["sale_date"])
        except ValueError as exc:
            raise DataQualityError("Invalid sale date") from exc

    def _load_dimensions(self, source: OperationalSource) -> None:
        self.connection.executemany(
            """
            INSERT INTO dim_customer(customer_id, customer_name, region)
            VALUES (?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                customer_name = excluded.customer_name,
                region = excluded.region
            """,
            [
                (r["customer_id"], r["customer_name"], r["region"])
                for r in source.customer_rows()
            ],
        )

        self.connection.executemany(
            """
            INSERT INTO dim_product(product_id, product_name, category)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                product_name = excluded.product_name,
                category = excluded.category
            """,
            [
                (r["product_id"], r["product_name"], r["category"])
                for r in source.product_rows()
            ],
        )

    def _load_date(self, sale_date: str) -> int:
        parsed = date.fromisoformat(sale_date)
        date_key = int(parsed.strftime("%Y%m%d"))

        self.connection.execute(
            """
            INSERT INTO dim_date(
                date_key, full_date, year_number, quarter_number,
                month_number, day_number
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date_key) DO NOTHING
            """,
            (
                date_key,
                parsed.isoformat(),
                parsed.year,
                ((parsed.month - 1) // 3) + 1,
                parsed.month,
                parsed.day,
            ),
        )
        return date_key

    def load_batch(
        self,
        source: OperationalSource,
    ) -> ETLStats:
        """
        Apply one incremental batch in a single warehouse transaction.

        The sequence watermark advances only when the batch commits. Fact
        records use source_sale_id as their business-level deduplication key.
        A newer CDC event replaces an older version of the same sale.
        """
        state = self.connection.execute(
            "SELECT last_change_seq FROM etl_state WHERE state_id = 1"
        ).fetchone()
        watermark = int(state["last_change_seq"])

        rows = source.extract_after(watermark)
        if not rows:
            return ETLStats()

        max_sequence = max(int(row["change_seq"]) for row in rows)

        loaded = 0
        unchanged = 0
        quarantined = 0
        skipped = 0

        with self.connection:
            self._load_dimensions(source)

            for row in rows:
                if row["status"] != "COMPLETED":
                    skipped += 1
                    continue

                try:
                    self._validate_record(row)
                except DataQualityError as exc:
                    self.connection.execute(
                        """
                        INSERT INTO etl_quarantine(
                            change_seq, source_sale_id, reason, original_record
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(change_seq) DO UPDATE SET
                            reason = excluded.reason,
                            original_record = excluded.original_record
                        """,
                        (
                            row["change_seq"],
                            row["source_sale_id"],
                            str(exc),
                            json.dumps(dict(row), sort_keys=True),
                        ),
                    )
                    quarantined += 1
                    continue

                customer = self.connection.execute(
                    """
                    SELECT customer_key
                    FROM dim_customer
                    WHERE customer_id = ?
                    """,
                    (row["customer_id"],),
                ).fetchone()

                product = self.connection.execute(
                    """
                    SELECT product_key
                    FROM dim_product
                    WHERE product_id = ?
                    """,
                    (row["product_id"],),
                ).fetchone()

                if customer is None or product is None:
                    reason = (
                        "Unknown customer dimension key"
                        if customer is None
                        else "Unknown product dimension key"
                    )
                    self.connection.execute(
                        """
                        INSERT INTO etl_quarantine(
                            change_seq, source_sale_id, reason, original_record
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(change_seq) DO UPDATE SET
                            reason = excluded.reason,
                            original_record = excluded.original_record
                        """,
                        (
                            row["change_seq"],
                            row["source_sale_id"],
                            reason,
                            json.dumps(dict(row), sort_keys=True),
                        ),
                    )
                    quarantined += 1
                    continue

                date_key = self._load_date(row["sale_date"])
                gross_cents = (
                    int(row["quantity"]) * int(row["unit_price_cents"])
                )

                cursor = self.connection.execute(
                    """
                    INSERT INTO fact_sales(
                        source_sale_id,
                        source_change_seq,
                        date_key,
                        customer_key,
                        product_key,
                        quantity,
                        unit_price_cents,
                        gross_cents,
                        source_changed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_sale_id) DO UPDATE SET
                        source_change_seq = excluded.source_change_seq,
                        date_key = excluded.date_key,
                        customer_key = excluded.customer_key,
                        product_key = excluded.product_key,
                        quantity = excluded.quantity,
                        unit_price_cents = excluded.unit_price_cents,
                        gross_cents = excluded.gross_cents,
                        source_changed_at = excluded.source_changed_at
                    WHERE excluded.source_change_seq >
                          fact_sales.source_change_seq
                    """,
                    (
                        row["source_sale_id"],
                        row["change_seq"],
                        date_key,
                        customer["customer_key"],
                        product["product_key"],
                        row["quantity"],
                        row["unit_price_cents"],
                        gross_cents,
                        row["changed_at"],
                    ),
                )

                if cursor.rowcount == 1:
                    loaded += 1
                else:
                    unchanged += 1

            # The watermark and fact changes commit together. If a database
            # operation fails, neither is committed.
            self.connection.execute(
                """
                UPDATE etl_state
                SET last_change_seq = ?,
                    last_successful_load = CURRENT_TIMESTAMP
                WHERE state_id = 1
                """,
                (max_sequence,),
            )

        return ETLStats(
            extracted=len(rows),
            loaded_or_updated=loaded,
            unchanged=unchanged,
            quarantined=quarantined,
            skipped=skipped,
        )

    def report_revenue_by_region(self) -> list[sqlite3.Row]:
        """OLAP aggregation: summarize facts across a customer dimension."""
        return self.connection.execute(
            """
            SELECT
                c.region,
                COUNT(*) AS sale_count,
                SUM(f.quantity) AS units_sold,
                SUM(f.gross_cents) AS revenue_cents
            FROM fact_sales AS f
            JOIN dim_customer AS c
                ON c.customer_key = f.customer_key
            GROUP BY c.region
            ORDER BY revenue_cents DESC
            """
        ).fetchall()

    def report_revenue_by_product(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                p.product_name,
                p.category,
                SUM(f.quantity) AS units_sold,
                SUM(f.gross_cents) AS revenue_cents
            FROM fact_sales AS f
            JOIN dim_product AS p
                ON p.product_key = f.product_key
            GROUP BY p.product_key, p.product_name, p.category
            ORDER BY revenue_cents DESC
            """
        ).fetchall()

    def quarantine_report(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT change_seq, source_sale_id, reason
            FROM etl_quarantine
            ORDER BY change_seq
            """
        ).fetchall()

    def fact_count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM fact_sales"
        ).fetchone()
        return int(row["total"])


def print_stats(label: str, stats: ETLStats) -> None:
    print(f"\n{label}")
    print(
        f"Extracted={stats.extracted}, "
        f"loaded/updated={stats.loaded_or_updated}, "
        f"unchanged={stats.unchanged}, "
        f"quarantined={stats.quarantined}, "
        f"skipped={stats.skipped}"
    )


def main() -> None:
    source = OperationalSource()
    warehouse = AnalyticalWarehouse()

    first_batch = warehouse.load_batch(source)
    print_stats("Initial ETL batch", first_batch)

    assert first_batch.extracted == 5
    assert first_batch.loaded_or_updated == 3
    assert first_batch.quarantined == 1
    assert first_batch.skipped == 1
    assert warehouse.fact_count() == 3

    # A correction arrives for an already loaded operational sale. The new
    # CDC event has a higher sequence number and replaces the older fact.
    source.add_change(
        source_sale_id="S1001",
        customer_id="C001",
        product_id="P100",
        sale_date="2026-10-01",
        quantity=3,
        unit_price_cents=75000,
        status="COMPLETED",
        changed_at="2026-10-06T09:00:00",
    )

    correction_batch = warehouse.load_batch(source)
    print_stats("Incremental correction batch", correction_batch)

    assert correction_batch.extracted == 1
    assert correction_batch.loaded_or_updated == 1
    assert warehouse.fact_count() == 3

    # No new source changes: an incremental run should do no work.
    empty_batch = warehouse.load_batch(source)
    print_stats("No-change batch", empty_batch)
    assert empty_batch.extracted == 0

    print("\nRevenue by region")
    for row in warehouse.report_revenue_by_region():
        revenue = row["revenue_cents"] / 100
        print(
            f"{row['region']}: {row['sale_count']} sales, "
            f"{row['units_sold']} units, revenue={revenue:.2f}"
        )

    print("\nRevenue by product")
    for row in warehouse.report_revenue_by_product():
        revenue = row["revenue_cents"] / 100
        print(
            f"{row['product_name']} ({row['category']}): "
            f"{row['units_sold']} units, revenue={revenue:.2f}"
        )

    print("\nQuarantined records")
    for row in warehouse.quarantine_report():
        print(
            f"Change {row['change_seq']} / {row['source_sale_id']}: "
            f"{row['reason']}"
        )

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
