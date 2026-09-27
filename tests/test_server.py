import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import server


class Detector:
    def inspect(self, text):
        return server.align_entities(text, [{"text": "秘密", "label": "SECRET"}])


class BridgeTests(unittest.TestCase):
    def test_cache_stores_only_hashes_and_independent_spans(self):
        detector = unittest.mock.Mock()
        detector.inspect.return_value = [{"start": 0, "end": 1, "label": "SECRET"}]
        cache = server.CachedDetector(detector)
        first = cache.inspect("not-retained")
        first[0]["start"] = 99
        self.assertEqual(cache.inspect("not-retained")[0]["start"], 0)
        detector.inspect.assert_called_once()
        self.assertNotIn("not-retained", repr(cache.entries))

    def test_cache_is_bounded(self):
        detector = unittest.mock.Mock()
        detector.inspect.return_value = [{"start": 0, "end": 1}]
        cache = server.CachedDetector(detector, max_entries=2, max_spans=1)
        cache.inspect("a")
        cache.inspect("b")
        cache.inspect("a")
        self.assertEqual(detector.inspect.call_count, 3)
        self.assertEqual(cache.span_count, 1)
        empty = server.CachedDetector(unittest.mock.Mock(inspect=lambda _: []), max_entries=2)
        for text in ["a", "b", "c"]:
            empty.inspect(text)
        self.assertEqual(len(empty.entries), 2)

    def test_cache_does_not_keep_failures(self):
        detector = unittest.mock.Mock()
        detector.inspect.side_effect = [ValueError("failed"), []]
        cache = server.CachedDetector(detector)
        with self.assertRaises(ValueError):
            cache.inspect("x")
        self.assertEqual(cache.inspect("x"), [])
        self.assertEqual(detector.inspect.call_count, 2)

    def test_setup_state_cannot_select_arbitrary_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = home / ".pentect" / "local-llm-masking"
            root.mkdir(parents=True)
            for state in [[], {"environment": "../../elsewhere"}, {"environment": "C:/arbitrary"}]:
                (root / "setup.json").write_text(json.dumps(state), encoding="utf-8")
                with patch.object(server.Path, "home", return_value=home), self.assertRaises(SystemExit):
                    server.main()

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
