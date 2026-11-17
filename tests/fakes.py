"""Small fakes for testing collectors without a network."""

import requests


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(
        self,
        payload=None,
        *,
        status_code=200,
        json_error=False,
        text="",
        url="",
    ):
        """Store the payload, the status code, the text and the final URL.

        json_error makes json() fail like requests does for a body that isn't JSON.
        """
        self._payload = payload
        self.text = text
        self.url = url
        self.status_code = status_code
        self.json_error = json_error
        self.content = b"" if payload is None and not json_error else b"x"

    def json(self):
        """Return the payload, or fail for a body that is not JSON."""
        if self.json_error:
            raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)
        return self._payload

    @property
    def ok(self):
        """Return True for a status below 400, like requests does."""
        return self.status_code < 400

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering every request with the given responses, in order.

    The last response repeats. A response that is an exception is raised instead.
    Every request is recorded in calls as (method, url, keyword arguments).
    """

    def __init__(self, *responses):
        """Store the responses."""
        self.responses = list(responses)
        self.calls = []

    def _answer(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        response = (
            self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        )
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, url, **kwargs):
        """Answer a GET."""
        return self._answer("GET", url, kwargs)

    def post(self, url, **kwargs):
        """Answer a POST."""
        return self._answer("POST", url, kwargs)

    def urls(self):
        """Return the URLs requested, in order."""
        return [url for _, url, _ in self.calls]
