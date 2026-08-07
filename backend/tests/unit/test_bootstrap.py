import backend.app


def test_backend_app_package_is_importable() -> None:
    assert backend.app.__name__ == "backend.app"
