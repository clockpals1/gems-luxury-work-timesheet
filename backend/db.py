"""Supabase Postgres adapter with a MongoDB-like async interface.

Each "collection" is stored in a table named ``gl_<collection>`` with two
columns: ``id TEXT PRIMARY KEY`` and ``doc JSONB``. The adapter translates the
small subset of MongoDB query/update operators used throughout
``server.py`` into Postgres SQL against the JSONB column so the existing
``motor``-style code in ``server.py`` keeps working without a rewrite.

Supported query operators:  equality, ``$ne``, ``$gte``, ``$gt``, ``$lt``,
``$lte``, ``$in``, ``$exists``.
Supported update operators: ``$set``, ``$inc``.
Supports ``upsert=True`` when filtering by ``id``.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Iterable, Optional

import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None

# Names of "collections" we need at startup so tables exist before first use.
KNOWN_COLLECTIONS: list[str] = [
    "users",
    "attendance_logs",
    "break_logs",
    "activity_logs",
    "admin_settings",
    "generated_products",
    "naming_families",
    "pricing_rules",
    "product_categories",
    "image_assets",
    "image_variations",
    "image_assignments",
    "export_logs",
    "prompt_templates",
]


def _safe_table(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"Invalid collection name: {name}")
    return f"gl_{name}"


async def init_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=10,
            statement_cache_size=0,  # required for Supavisor transaction/session pooler
            ssl="require",           # Supabase pooler enforces SSL
            command_timeout=30,
        )
        await _ensure_schema()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _ensure_schema() -> None:
    assert _pool is not None
    async with _pool.acquire() as conn:
        for c in KNOWN_COLLECTIONS:
            tbl = _safe_table(c)
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id   TEXT PRIMARY KEY,
                    doc  JSONB NOT NULL
                );
                """
            )
        # Helpful indexes for hot paths
        helpful_indexes = [
            ("gl_users", "email", "(doc->>'email')"),
            ("gl_attendance_logs", "user_id", "(doc->>'user_id')"),
            ("gl_attendance_logs", "punch_out", "(doc->>'punch_out')"),
            ("gl_break_logs", "attendance_id", "(doc->>'attendance_id')"),
            ("gl_break_logs", "end", "((doc->>'end'))"),
            ("gl_generated_products", "generated_by_user_id", "(doc->>'generated_by_user_id')"),
            ("gl_generated_products", "generated_at", "(doc->>'generated_at')"),
            ("gl_image_assets", "status", "(doc->>'status')"),
            ("gl_activity_logs", "timestamp", "(doc->>'timestamp')"),
            ("gl_prompt_templates", "key", "(doc->>'key')"),
        ]
        for tbl, col, expr in helpful_indexes:
            idx = f"idx_{tbl}_{col}"
            try:
                await conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl} {expr};")
            except Exception as e:  # pragma: no cover - non-fatal
                logger.warning("index %s create failed: %s", idx, e)


# ---------------------------------------------------------------------------
# Filter / projection translation
# ---------------------------------------------------------------------------

def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def _build_where(filter_: dict | None) -> tuple[str, list[Any]]:
    """Translate a Mongo-style filter into a SQL WHERE clause.

    Returns ("WHERE ..." or "", params).
    """
    if not filter_:
        return "", []
    clauses: list[str] = []
    params: list[Any] = []

    def _next() -> str:
        return f"${len(params) + 1}"

    for field, cond in filter_.items():
        # use indexed `id` column for id lookups
        if field == "id" and _is_scalar(cond):
            params.append(cond)
            clauses.append(f"id = {_next()}")
            continue

        col_text = f"doc->>'{field}'"

        if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
            for op, val in cond.items():
                if op == "$ne":
                    if isinstance(val, bool):
                        params.append(val)
                        clauses.append(f"({col_text})::boolean IS DISTINCT FROM {_next()}")
                    elif isinstance(val, (int, float)):
                        params.append(val)
                        clauses.append(f"({col_text})::numeric IS DISTINCT FROM {_next()}")
                    else:
                        params.append(val)
                        clauses.append(f"{col_text} IS DISTINCT FROM {_next()}")
                elif op in ("$gte", "$gt", "$lte", "$lt"):
                    sym = {"$gte": ">=", "$gt": ">", "$lte": "<=", "$lt": "<"}[op]
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        params.append(val)
                        clauses.append(f"({col_text})::numeric {sym} {_next()}")
                    else:
                        params.append(val)
                        clauses.append(f"{col_text} {sym} {_next()}")
                elif op == "$in":
                    arr = list(val)
                    params.append(arr)
                    # cast to text[] for string comparisons; works for our usage
                    clauses.append(f"{col_text} = ANY({_next()}::text[])")
                elif op == "$exists":
                    if val:
                        clauses.append(f"doc ? '{field}'")
                    else:
                        clauses.append(f"NOT (doc ? '{field}')")
                else:
                    raise NotImplementedError(f"Unsupported operator {op}")
        else:
            # equality
            if cond is None:
                clauses.append(f"({col_text} IS NULL)")
            elif isinstance(cond, bool):
                params.append(cond)
                clauses.append(f"({col_text})::boolean = {_next()}")
            elif isinstance(cond, (int, float)):
                params.append(cond)
                clauses.append(f"({col_text})::numeric = {_next()}")
            else:
                params.append(cond)
                clauses.append(f"{col_text} = {_next()}")

    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _apply_projection(doc: dict | None, projection: dict | None) -> dict | None:
    if doc is None:
        return None
    if not projection:
        return doc
    proj = {k: v for k, v in projection.items() if k != "_id"}
    if not proj:
        return doc
    has_include = any(v in (1, True) for v in proj.values())
    if has_include:
        keys = [k for k, v in proj.items() if v in (1, True)]
        return {k: doc[k] for k in keys if k in doc}
    excluded = {k for k, v in proj.items() if v in (0, False)}
    return {k: v for k, v in doc.items() if k not in excluded}


# ---------------------------------------------------------------------------
# Update result placeholder
# ---------------------------------------------------------------------------

class _UpdateResult:
    def __init__(self, matched: int, modified: int = 0):
        self.matched_count = matched
        self.modified_count = modified


# ---------------------------------------------------------------------------
# Cursor (lazy find)
# ---------------------------------------------------------------------------

class _Cursor:
    def __init__(self, collection: "_Collection", filter_: dict | None, projection: dict | None):
        self._collection = collection
        self._filter = filter_ or {}
        self._projection = projection
        self._sort: list[tuple[str, int]] = []

    def sort(self, field: str, direction: int = 1) -> "_Cursor":
        self._sort.append((field, direction))
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return await self._collection._run_find(
            self._filter, self._projection, self._sort, length
        )


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

class _Collection:
    def __init__(self, name: str):
        self.name = name
        self.table = _safe_table(name)

    async def _conn(self):
        if _pool is None:
            raise RuntimeError("DB pool not initialized")
        return _pool

    async def find_one(
        self, filter_: dict | None = None, projection: dict | None = None
    ) -> dict | None:
        where, params = _build_where(filter_)
        sql = f"SELECT doc FROM {self.table} {where} LIMIT 1"
        pool = await self._conn()
        async with pool.acquire() as c:
            row = await c.fetchrow(sql, *params)
        if not row:
            return None
        doc = row["doc"]
        if isinstance(doc, str):
            doc = json.loads(doc)
        return _apply_projection(doc, projection)

    def find(
        self, filter_: dict | None = None, projection: dict | None = None
    ) -> _Cursor:
        return _Cursor(self, filter_, projection)

    async def _run_find(
        self,
        filter_: dict | None,
        projection: dict | None,
        sort: list[tuple[str, int]] | None,
        limit: int | None,
    ) -> list[dict]:
        where, params = _build_where(filter_)
        order = ""
        if sort:
            parts = []
            for f, d in sort:
                direction = "DESC" if d < 0 else "ASC"
                parts.append(f"doc->>'{f}' {direction}")
            order = "ORDER BY " + ", ".join(parts)
        lim = f"LIMIT {int(limit)}" if limit else ""
        sql = f"SELECT doc FROM {self.table} {where} {order} {lim}".strip()
        pool = await self._conn()
        async with pool.acquire() as c:
            rows = await c.fetch(sql, *params)
        out: list[dict] = []
        for r in rows:
            doc = r["doc"]
            if isinstance(doc, str):
                doc = json.loads(doc)
            out.append(_apply_projection(doc, projection))
        return out

    async def count_documents(self, filter_: dict | None = None) -> int:
        where, params = _build_where(filter_)
        sql = f"SELECT COUNT(*) AS n FROM {self.table} {where}"
        pool = await self._conn()
        async with pool.acquire() as c:
            row = await c.fetchrow(sql, *params)
        return int(row["n"]) if row else 0

    async def insert_one(self, doc: dict) -> dict:
        if "id" not in doc:
            raise ValueError("doc must include 'id' field")
        pool = await self._conn()
        payload = json.dumps(doc, default=str)
        sql = f"INSERT INTO {self.table} (id, doc) VALUES ($1, $2::jsonb)"
        async with pool.acquire() as c:
            await c.execute(sql, doc["id"], payload)
        return doc

    async def update_one(
        self,
        filter_: dict,
        update: dict,
        upsert: bool = False,
    ) -> _UpdateResult:
        set_obj = update.get("$set") or {}
        inc_obj = update.get("$inc") or {}

        # Build SET expression incrementally
        set_doc_expr = "doc"
        params: list[Any] = []

        def _next() -> str:
            return f"${len(params) + 1}"

        # Apply $inc first
        for field, delta in inc_obj.items():
            params.append(delta)
            set_doc_expr = (
                f"jsonb_set({set_doc_expr}, '{{{field}}}', "
                f"to_jsonb(COALESCE(({set_doc_expr}->>'{field}')::numeric, 0) + {_next()}))"
            )
        # Then merge $set on top
        if set_obj:
            params.append(json.dumps(set_obj, default=str))
            set_doc_expr = f"({set_doc_expr} || {_next()}::jsonb)"

        where, where_params = _build_where(filter_)
        # Re-number where params relative to current params length
        if where_params:
            offset = len(params)
            # rewrite $N -> $(N+offset)
            def _shift(m: re.Match) -> str:
                n = int(m.group(1))
                return f"${n + offset}"

            where = re.sub(r"\$(\d+)", _shift, where)
            params.extend(where_params)

        sql = f"UPDATE {self.table} SET doc = {set_doc_expr} {where}"
        pool = await self._conn()
        async with pool.acquire() as c:
            res = await c.execute(sql, *params)
        # res like 'UPDATE N'
        try:
            matched = int(res.rsplit(" ", 1)[1])
        except Exception:
            matched = 0

        if matched == 0 and upsert:
            # Build a doc from $set + filter equality keys + $inc fields (default 0 + delta)
            new_doc: dict[str, Any] = {}
            # copy equality fields from filter
            for k, v in (filter_ or {}).items():
                if _is_scalar(v):
                    new_doc[k] = v
            for k, v in inc_obj.items():
                new_doc[k] = v
            new_doc.update(set_obj)
            if "id" not in new_doc:
                raise ValueError("upsert requires id in filter or $set")
            await self.insert_one(new_doc)
            return _UpdateResult(matched=1, modified=1)
        return _UpdateResult(matched=matched, modified=matched)

    async def delete_one(self, filter_: dict) -> _UpdateResult:
        where, params = _build_where(filter_)
        sql = f"DELETE FROM {self.table} {where}"
        pool = await self._conn()
        async with pool.acquire() as c:
            res = await c.execute(sql, *params)
        try:
            n = int(res.rsplit(" ", 1)[1])
        except Exception:
            n = 0
        return _UpdateResult(matched=n, modified=n)


# ---------------------------------------------------------------------------
# Database facade
# ---------------------------------------------------------------------------

class _Database:
    def __init__(self):
        self._collections: dict[str, _Collection] = {}

    def __getattr__(self, name: str) -> _Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = _Collection(name)
        return self._collections[name]


db = _Database()


def get_db() -> _Database:
    return db
