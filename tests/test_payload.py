import unittest

from kyanbasu.payload import build_payload


class TestPayload(unittest.TestCase):
    def test_build_payload_edges_and_maps(self):
        tasks = [
            {
                "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "short": "aaaaaaaa",
                "desc": "Alpha",
                "project": "Work",
                "tags": ["p1"],
                "depends": [],
                "due": None,
            },
            {
                "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "short": "bbbbbbbb",
                "desc": "Beta",
                "project": "Work",
                "tags": [],
                "depends": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "not-in-payload"],
                "due": "20260220T000000Z",
            },
        ]

        payload = build_payload(tasks)

        self.assertEqual(len(payload["tasks"]), 2)
        self.assertEqual(payload["tasks"][0]["has_depends"], False)
        self.assertEqual(payload["tasks"][1]["has_depends"], True)
        self.assertEqual(
            payload["graph"]["edges"],
            [{"from": "bbbbbbbb", "to": "aaaaaaaa"}],
        )
        self.assertEqual(payload["graph"]["parent_current_deps"], {"bbbbbbbb": ["aaaaaaaa"]})
        self.assertEqual(payload["graph"]["child_to_parents"], {"aaaaaaaa": ["bbbbbbbb"]})


if __name__ == "__main__":
    unittest.main()
