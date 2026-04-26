from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardFilters:
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
