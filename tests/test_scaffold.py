import doma


def test_package_importable() -> None:
    assert doma.__version__ == "0.1.0"
