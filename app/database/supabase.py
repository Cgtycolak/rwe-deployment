"""Read-only engine for the Supabase analytics schemas (meteologica, openmeteo, epias)."""
import os

from sqlalchemy import create_engine, pool

_supabase_engine = None


def get_supabase_engine():
    global _supabase_engine
    if _supabase_engine is None:
        sb_user = os.getenv("SUPABASE_USER")
        sb_password = os.getenv("SUPABASE_PASSWORD")
        if not sb_user or not sb_password:
            raise RuntimeError("SUPABASE_USER / SUPABASE_PASSWORD not set")
        _supabase_engine = create_engine(
            f"postgresql+psycopg2://{sb_user}:{sb_password}"
            "@aws-0-us-east-2.pooler.supabase.com:5432/postgres",
            poolclass=pool.QueuePool,
            pool_size=3,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
    return _supabase_engine
