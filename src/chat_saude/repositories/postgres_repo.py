from sqlalchemy import text

from chat_saude.infrastructure.database.postgres import get_engine


class PostgresRepository:
    """Repository for PostgreSQL data access using the shared engine."""

    def __init__(self):
        self._engine = get_engine()

    def execute_query(self, query: str):
        """Execute a SQL query and return the result rows."""
        with self._engine.connect() as conn:
            result = conn.execute(text(query))
            return result.fetchall()
