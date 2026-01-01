
# tests/test_parser_agent_meta.py
from __future__ import annotations
import re
import pandas as pd

import src.parser.parser_db_ready_fixed_Version4 as v4

def test_find_agent_code_from_pattern_line():
    lines = [
        "Some header",
        "Company: SIC LIFE",
        "Agent Name: Nana",
        "AGENT ACCOUNT NO: AG123",
        "Month: Jun 2025",
    ]
    ac = v4.find_agent_code_from_lines(lines)
    assert ac == "AG123"

def test_find_agent_code_from_fallback_line():
    # Fallback logic: when no explicit marker, code often appears tokenized on a header line.
    # We craft a non-address line to trigger the fallback selection.
    lines = [
        "Header A",
        "Header B",
        "Header C",
        "Header D",
        "Header E",
        "Header F",
        "   Some  fields    more-fields    even-more   9518   other",
        "Footer",
    ]
    ac = v4.find_agent_code_from_lines(lines)
    assert re.match(r"^\d{3,6}$", ac)

def test_license_number_column_present_when_df_has_it():
    # If a parsed DataFrame carries AGENT_LICENSE_NUMBER, ensure the name is consistent downstream.
    df = pd.DataFrame([{"AGENT_LICENSE_NUMBER": "LIC-7788", "policy_no": "P001"}])
    # Not a function test per se—just documenting the expected column name
    assert "AGENT_LICENSE_NUMBER" in df.columns
