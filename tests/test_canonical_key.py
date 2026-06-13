from domain.product.model import ProductRatingDimension
from services.rating import canonical_dim_key


def test_order_independent():
    assert canonical_dim_key({"sex": "M", "age": 30}) == canonical_dim_key(
        {"age": 30, "sex": "M"}
    )


def test_normalizes_by_declared_type():
    dims = [
        ProductRatingDimension(name="age", data_type="int", position=0),
        ProductRatingDimension(name="sex", data_type="str", position=1),
    ]
    # int → plain int; str → upper + strip
    assert canonical_dim_key({"age": 30, "sex": "m "}, dims) == "age=30|sex=M"
