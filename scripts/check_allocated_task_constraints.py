import sys
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.config import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT conname FROM pg_constraint WHERE conrelid = 'allocated_tasks'::regclass AND contype = 'c'")
    ).all()
    print(rows)
