from anton.llm import LlamaClient


def test_extract_json_accepts_fenced_response() -> None:
    assert LlamaClient._extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_finds_embedded_object() -> None:
    assert LlamaClient._extract_json('Here it is: {"count": 2}') == {"count": 2}
