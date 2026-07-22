import threading

import pytest

from backend.app.services.message_transformation_service import OllamaTransformationGenerator


def test_ollama_stream_closes_and_does_not_retry_after_visible_token(monkeypatch):
    cancel = threading.Event(); tokens = []; instances = []

    class Iterator:
        def __init__(self): self.index = 0; self.closed = False
        def __iter__(self): return self
        def __next__(self):
            self.index += 1
            if self.index == 1:
                return "first"
            if self.index == 2: return "second"
            raise StopIteration
        def close(self): self.closed = True

    class FakeOllama:
        def __init__(self, **_): self.iterator = Iterator(); self.stream_calls = 0; instances.append(self)
        def stream(self, _prompt): self.stream_calls += 1; return self.iterator

    monkeypatch.setattr("langchain_ollama.OllamaLLM", FakeOllama)
    with pytest.raises(RuntimeError, match="Local generation failed"):
        OllamaTransformationGenerator("local-test").stream_generate("prompt", cancel_event=cancel, token_callback=lambda value:(tokens.append(value),cancel.set()))
    assert tokens == ["first"]
    assert len(instances) == 1 and instances[0].stream_calls == 1
    assert instances[0].iterator.closed is True


def test_ollama_stream_collects_real_chunks(monkeypatch):
    class FakeOllama:
        def __init__(self, **_): pass
        def stream(self, _prompt): return iter(["Grounded ", "answer [1]"])

    monkeypatch.setattr("langchain_ollama.OllamaLLM", FakeOllama)
    tokens=[]
    result=OllamaTransformationGenerator("local-test").stream_generate("prompt",token_callback=tokens.append)
    assert result == "Grounded answer [1]"
    assert tokens == ["Grounded ", "answer [1]"]
