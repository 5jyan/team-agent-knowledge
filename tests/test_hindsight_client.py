from __future__ import annotations

import unittest

from scripts.reconcile import HindsightClient, HindsightError


class Response:
    def __init__(self, payload=None, status_code: int = 200, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"" if payload is None else b"{}"

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class Session:
    def __init__(self):
        self.calls = []
        self.responses = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class HindsightClientTests(unittest.TestCase):
    def test_document_endpoints_and_payload_match_v11_contract(self):
        session = Session()
        session.responses.extend(
            [
                Response({"items": [{"id": "COMP-001"}], "total": 1}),
                Response({"success": True}),
                Response({"success": True}),
            ]
        )
        client = HindsightClient("http://127.0.0.1:8888", session=session)
        self.assertEqual(client.list_documents("team-compiler"), [{"id": "COMP-001"}])
        client.upsert_document("team-compiler", "COMP-001", "id: COMP-001\n", {"managed_by": "team-agent-knowledge"})
        client.delete_document("team-compiler", "COMP-001")

        self.assertEqual(session.calls[0][0:2], ("GET", "http://127.0.0.1:8888/v1/default/banks/team-compiler/documents"))
        post = session.calls[1]
        self.assertEqual(post[0], "POST")
        self.assertEqual(post[2]["json"]["async"], False)
        self.assertEqual(post[2]["json"]["items"][0]["document_id"], "COMP-001")
        self.assertEqual(session.calls[2][0], "DELETE")

    def test_http_failure_is_explicit(self):
        session = Session()
        session.responses.append(Response({"detail": "down"}, status_code=503, text="down"))
        with self.assertRaises(HindsightError):
            HindsightClient(session=session).list_documents("team-compiler")


if __name__ == "__main__":
    unittest.main()
