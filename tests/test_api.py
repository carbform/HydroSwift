import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swift_app.api import WrisClient

def test_wris_client_init():
    client = WrisClient()
    assert client.session is not None
    assert "User-Agent" in client.session.headers

@patch("swift_app.wris_client.requests.Session.post")
def test_wris_check_api(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "success"}

    client = WrisClient()
    assert client.check_api() == True

    mock_post.return_value.status_code = 500
    assert client.check_api() == False

@patch("swift_app.wris_client.requests.Session.post")
def test_get_metadata_parser(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"station_code": "S1", "station_Name": "Test Station"}
        ]
    }
    mock_post.return_value = mock_response

    client = WrisClient()
    res = client.get_metadata("S1", "C1")
    assert res is not None
    assert res["station_Name"] == "Test Station"
