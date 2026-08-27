from app.numbers import mask_number, normalize_uk_number


def test_normalizes_common_uk_formats():
    assert normalize_uk_number("07123 456789") == "07123456789"
    assert normalize_uk_number("+44 7123 456789") == "07123456789"
    assert normalize_uk_number("447123456789") == "07123456789"
    assert normalize_uk_number("020 7946 0958") == "02079460958"


def test_adds_missing_leading_zero():
    assert normalize_uk_number("7487723751") == "07487723751"
    assert normalize_uk_number("2079460958") == "02079460958"
    assert normalize_uk_number("1912345678") == "01912345678"


def test_handles_excel_number_artifacts():
    assert normalize_uk_number("7487723751.0") == "07487723751"
    assert normalize_uk_number("7.487723751E9") == "07487723751"


def test_rejects_non_uk_or_empty():
    assert normalize_uk_number("") is None
    assert normalize_uk_number("n/a") is None
    assert normalize_uk_number("not a number") is None
    assert normalize_uk_number("+1 202 555 0100") is None


def test_masks_numbers():
    assert mask_number("07123456789") == "0712****789"
