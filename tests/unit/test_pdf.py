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


def test_extract_text_returns_empty_string_on_invalid_pdf(monkeypatch) -> None:
    monkeypatch.setattr(pdf, "PdfReader", BrokenReader)

    assert pdf.extract_text(b"not a pdf") == ""


def test_extract_text_uses_first_and_last_pages_without_overlap(monkeypatch) -> None:
    monkeypatch.setattr(pdf, "PdfReader", FakeReader)

    text = pdf.extract_text(b"%PDF", first_pages=2, last_pages=2)

    assert "Page 1 text" in text
    assert "Page 2 text" in text
    assert "Page 4 text" in text
    assert "Page 5 text" in text
    assert "Page 3 text" not in text
