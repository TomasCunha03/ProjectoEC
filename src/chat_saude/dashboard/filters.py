"""
Dashboard filter definitions.

Provides the immutable ``DashboardFilters`` dataclass that carries all
user-supplied filter values from the UI / chat layer down to the query
builders and chart renderers.  Using a frozen dataclass makes it safe to
use as a ``@st.cache_data`` key.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardFilters:
    """Immutable snapshot of every filter the user has applied.

    Fields are grouped by dataset so that each query builder only reads
    the fields relevant to its own table:

    * ``global_*``       — ``global_health_stats`` table
    * ``immunization_*`` / ``vaccine_code`` — immunization fact/dim tables
    * ``chronic_*``      — ``chronic_disease_indicators`` table (US states)
    * ``top_n``          — shared "show top N" control used across chart types
    """

    global_start_year: int | None = None
    global_end_year: int | None = None
    global_country: str | None = None
    global_disease_name: str | None = None
    global_disease_category: str | None = None
    immunization_start_year: int | None = None
    immunization_end_year: int | None = None
    vaccine_code: str | None = None
    top_n: int | None = None
    chronic_start_year: int | None = None
    chronic_end_year: int | None = None
    chronic_location: str | None = None
    chronic_topic: str | None = None
