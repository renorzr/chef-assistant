import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import load_env_file

load_env_file()


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def get_database_url() -> str:
    return normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "sqlite:///./chef_assistant.db",
        )
    )


DATABASE_URL = get_database_url()

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_common_migrations() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        if "meal_plans" in tables:
            meal_plan_cols = {col["name"] for col in inspector.get_columns("meal_plans")}
            if "expected_finish_at" not in meal_plan_cols:
                conn.execute(text("ALTER TABLE meal_plans ADD COLUMN expected_finish_at TIMESTAMP NULL"))
                migration_sql = (
                    text("UPDATE meal_plans SET expected_finish_at = datetime(created_at, '+24 hours') WHERE expected_finish_at IS NULL")
                    if DATABASE_URL.startswith("sqlite")
                    else text("UPDATE meal_plans SET expected_finish_at = created_at + INTERVAL '24 hours' WHERE expected_finish_at IS NULL")
                )
                conn.execute(migration_sql)
            if "cancelled_at" not in meal_plan_cols:
                conn.execute(text("ALTER TABLE meal_plans ADD COLUMN cancelled_at TIMESTAMP NULL"))

        if "recipe_ingredients" in tables:
            recipe_ing_cols = {col["name"] for col in inspector.get_columns("recipe_ingredients")}
            if "note" not in recipe_ing_cols:
                conn.execute(text("ALTER TABLE recipe_ingredients ADD COLUMN note TEXT NULL"))
            if "optional" not in recipe_ing_cols:
                conn.execute(text("ALTER TABLE recipe_ingredients ADD COLUMN optional INTEGER NOT NULL DEFAULT 0"))


def run_sqlite_migrations() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if "recipes" in tables:
            recipe_cols = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info('recipes')")
            }
            if "cover_image_url" not in recipe_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE recipes ADD COLUMN cover_image_url VARCHAR(1000)"
                )

        if "recipe_steps" in tables:
            step_cols = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info('recipe_steps')")
            }
            if "image_url" not in step_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE recipe_steps ADD COLUMN image_url VARCHAR(1000)"
                )

        if "meal_plans" in tables:
            meal_plan_cols = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info('meal_plans')")
            }
            if "expected_finish_at" not in meal_plan_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE meal_plans ADD COLUMN expected_finish_at TIMESTAMP"
                )
                conn.exec_driver_sql(
                    "UPDATE meal_plans SET expected_finish_at = datetime(created_at, '+24 hours') WHERE expected_finish_at IS NULL"
                )
            if "cancelled_at" not in meal_plan_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE meal_plans ADD COLUMN cancelled_at TIMESTAMP"
                )

        if "recipe_ingredients" in tables:
            recipe_ing_cols = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info('recipe_ingredients')")
            }
            if "note" not in recipe_ing_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE recipe_ingredients ADD COLUMN note TEXT"
                )
            if "optional" not in recipe_ing_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE recipe_ingredients ADD COLUMN optional INTEGER NOT NULL DEFAULT 0"
                )


def cleanup_placeholder_media() -> None:
    with engine.begin() as conn:
        pattern = "https://example.com/%"
        conn.execute(
            text("UPDATE recipes SET cover_image_url = NULL WHERE cover_image_url LIKE :pattern"),
            {"pattern": pattern},
        )
        conn.execute(
            text("UPDATE recipes SET source_url = NULL WHERE source_url LIKE :pattern"),
            {"pattern": pattern},
        )
        conn.execute(
            text("UPDATE recipe_steps SET image_url = NULL WHERE image_url LIKE :pattern"),
            {"pattern": pattern},
        )
        conn.execute(
            text("DELETE FROM recipe_media WHERE url LIKE :pattern"),
            {"pattern": pattern},
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
