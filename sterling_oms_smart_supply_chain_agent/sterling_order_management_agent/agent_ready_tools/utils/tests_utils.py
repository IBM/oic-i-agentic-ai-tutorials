from requests import Response


def make_fake_response(status_code: int, url: str, text: str = "Service Unavailable") -> Response:
    """Helper to create a fake requests.Response."""
    resp = Response()
    resp.status_code = status_code
    resp.url = url
    resp.reason = text
    return resp
