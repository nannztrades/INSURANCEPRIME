
import pytest

# If this import path differs, adjust to your layout.
from src.util.periods import normalize_month_param

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2025-6",   "2025-06"),
        ("2025/06",  "2025-06"),
        ("Jun 2025", "2025-06"),
        ("June 2025","2025-06"),
        ("COM_2025-06","2025-06"),
        ("2025-06",  "2025-06"),   # idempotent
        ("  Jun 2025  ", "2025-06"),
    ],
)
def test_various_inputs_to_canonical(raw, expected):
    assert normalize_month_param(raw) == expected

@pytest.mark.parametrize("bad", [None, "", "2025-13", "2025-00", "2025/00", "Foo 2025", "2025--06"])
def test_invalid_inputs_return_none(bad):
    assert normalize_month_param(bad) is None

def test_idempotence():
    assert normalize_month_param("2025-06") == "2025-06"
