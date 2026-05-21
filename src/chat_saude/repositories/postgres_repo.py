"""
PostgreSQL repository abstraction for chat_saude.

Wraps the shared SQLAlchemy engine (managed by the infrastructure layer) to
provide a simple interface for executing read queries without exposing engine
or session management to callers.
"""

from sqlalchemy import text

from chat_saude.infrastructure.database.postgres import get_engine


class PostgresRepository:
    """Repository for PostgreSQL data access using the shared engine.

    Each instance holds a reference to the shared engine; connections are drawn
    from SQLAlchemy's connection pool on demand and returned automatically when
    the context manager exits.
    """

    def __init__(self):
        self._engine = get_engine()

    def execute_query(self, query: str):
        """Execute a SQL query and return all result rows.

        The query string is wrapped in sqlalchemy.text() so that it is treated
        as a textual SQL expression rather than a raw string, which is required
        by SQLAlchemy 2.x.

        Args:
            query: A valid SQL SELECT statement as a plain string.

        Returns:
            A list of SQLAlchemy Row objects; access columns by name or index.
        """
        with self._engine.connect() as conn:
            result = conn.execute(text(query))
            return result.fetchall()
