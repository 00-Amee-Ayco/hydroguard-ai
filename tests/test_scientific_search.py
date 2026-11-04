"""Unit tests for scientific-search SQL safety; no live Zetaris required."""
import pytest
from hydroguard.data.scientific_search import make_scientific_sql


def test_scientific_sql_water():
    sql, terms = make_scientific_sql("HYDROGUARD.scientific_abstracts", "Water", "river water")
    assert terms == ["water", "river"]
    assert "FROM HYDROGUARD.scientific_abstracts" in sql
    assert "LOWER(abstract) LIKE '%water%'" in sql
    assert "LIMIT 10" in sql


@pytest.mark.parametrize("table, domain, query", [
    ("bad;DROP", "Water", "water"),
    ("HYDROGUARD.scientific_abstracts", "Water", "water'; DROP TABLE"),
    ("HYDROGUARD.scientific_abstracts", "Unknown", "water"),
    ("HYDROGUARD.scientific_abstracts", "Water", "notrecognized"),
])
def test_scientific_sql_rejects_invalid_input(table, domain, query):
    with pytest.raises(ValueError):
        make_scientific_sql(table, domain, query)
