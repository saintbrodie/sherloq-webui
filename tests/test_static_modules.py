from fastapi.testclient import TestClient

from web.main import app


def test_plugin_runtime_load_order_and_assets() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    expected_order = [
        "/app.js",
        "/advanced-tools.js",
        "/plugin-runtime.js",
        "/plots.js",
        "/utility-tools.js",
        "/ela-tools.js",
        "/external-tools.js",
        "/history.js",
    ]
    offsets = [html.index(f'src="{path}"') for path in expected_order]
    assert offsets == sorted(offsets)

    for path in expected_order:
        asset = client.get(path)
        assert asset.status_code == 200, path
        assert asset.text.strip(), path
