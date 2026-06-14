from datetime import date

import pytest

from observability.exceptions import ValidationError
from services.rating import age_last_birthday


def test_birthday_not_yet_this_year():
    assert age_last_birthday(date(1990, 5, 2), date(2026, 1, 1)) == 35


def test_birthday_already_passed():
    assert age_last_birthday(date(1990, 1, 1), date(2026, 6, 1)) == 36


def test_age_zero():
    assert age_last_birthday(date(2025, 7, 1), date(2026, 1, 1)) == 0


def test_as_of_before_dob_raises():
    with pytest.raises(ValidationError):
        age_last_birthday(date(2026, 1, 1), date(2025, 1, 1))


def test_leap_day_birthday():
    # Born Feb 29; on Feb 28 the birthday hasn't "occurred" → age 25.
    assert age_last_birthday(date(2000, 2, 29), date(2026, 2, 28)) == 25
