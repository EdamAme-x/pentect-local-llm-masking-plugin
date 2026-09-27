import io
import json
import unittest
from unittest.mock import patch
import server


class Detector:
    def inspect(self, text):
        return server.align_entities(text, [{"text": "秘密", "label": "SECRET"}])


class BridgeTests(unittest.TestCase):
    def test_utf8_and_repeated_values(self):
        spans = server.align_entities("🙂秘密/秘密", [{"text": "秘密", "label": "SECRET"}])
        self.assertEqual([(s["start"], s["end"]) for s in spans], [(4, 10), (11, 17)])

    def test_hallucination_rejected(self):
        with self.assertRaises(ValueError):
            server.align_entities("safe", [{"text": "invented", "label": "SECRET"}])

    def test_invalid_entities(self):
        for value in [None, {}, [None], [{"text": "", "label": "SECRET"}],
                      [{"text": "x", "label": []}], [{"text": "x", "label": "BAD"}],
                      [{"text": "x", "label": "SECRET", "extra": 1}]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.align_entities("x", value)

    def test_empty_and_dedup(self):
        self.assertEqual(server.align_entities("safe", []), [])
        entity = {"text": "x", "label": "SECRET"}
        self.assertEqual(len(server.align_entities("x", [entity, entity])), 1)

    def test_span_cap(self):
        with self.assertRaises(ValueError):
            server.align_entities("x" * 4097, [{"text": "x", "label": "SECRET"}])

    def test_protocol(self):
        request = {"schema": server.SCHEMA, "id": 7, "hook": "inspect", "payload": {"text": "秘密"}}
        response = server.handle(Detector(), request)
        self.assertEqual(response["id"], 7)
        self.assertNotIn("秘密", json.dumps(response, ensure_ascii=False))
        for key, value in [("id", True), ("hook", "bad"), ("payload", {}), ("schema", "bad")]:
            with self.assertRaises(ValueError):
                server.handle(Detector(), dict(request, **{key: value}))

    def test_windows_translate_byte_offsets(self):
        detector = object.__new__(server.LocalLLM)
        detector.extract = lambda text: server.align_entities(text, [{"text": "秘密", "label": "SECRET"}]) if "秘密" in text else []
        text = "あ" * 3100 + "秘密"
        self.assertEqual([(s["start"], s["end"]) for s in detector.inspect(text)], [(9300, 9306)])
        self.assertEqual(detector.inspect(""), [])

    def test_errors_do_not_echo_input(self):
        stream = io.TextIOWrapper(io.BytesIO(b'{"secret":"do-not-echo"}\n'))
        output = io.StringIO()
        with patch.object(server.sys, "stdin", stream), patch.object(server.sys, "stdout", output):
            server.serve(Detector())
        result = json.loads(output.getvalue())
        self.assertEqual(result["error"]["code"], "inference_failed")
        self.assertNotIn("do-not-echo", output.getvalue())


if __name__ == "__main__":
    unittest.main()
