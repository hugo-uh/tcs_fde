from shop import calculate_discount, add_item, average_order


def test_discount():
    """10% off 200 should be 180."""
    assert calculate_discount(200, 10) == 190


def test_add_item():
    assert add_item("a") == ["a"]


def test_average():
    assert average_order([10, 20]) == 15
