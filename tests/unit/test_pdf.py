import litresearch.pdf as pdf


class FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self) -> str:
        return self._text


class FakeReader:
    def __init__(self, _stream) -> None:
        self.pages = [
            FakePage("Page 1 text"),
            FakePage("Page 2 text"),
            FakePage("Page 3 text"),
            FakePage("Page 4 text"),
            FakePage("Page 5 text"),
        ]


class BrokenReader:
    def __init__(self, _stream) -> None:
        raise ValueError("bad pdf")


def test_extract_text_returns_none_on_invalid_pdf(monkeypatch) -> None:
    monkeypatch.setattr(pdf, "PdfReader", BrokenReader)

    assert pdf.extract_text(b"not a pdf") is None


def test_extract_text_returns_all_pages_within_budget(monkeypatch) -> None:
    monkeypatch.setattr(pdf, "PdfReader", FakeReader)

    text = pdf.extract_text(b"%PDF", token_budget=10000)
    assert text is not None
    assert "Page 1 text" in text
    assert "Page 2 text" in text
    assert "Page 3 text" in text
    assert "Page 4 text" in text
    assert "Page 5 text" in text
