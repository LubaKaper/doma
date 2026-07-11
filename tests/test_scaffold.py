import hunt


def test_package_importable() -> None:
    assert hunt.__version__ == "0.1.0"
