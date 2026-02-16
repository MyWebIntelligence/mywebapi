from app.db.models import Paragraph


def test_paragraph_has_embedding_property():
    paragraph = Paragraph(
        id=1,
        expression_id=1,
        text="Sample text",
        text_hash="hash",
        position=0,
        embedding=[0.1, 0.2, 0.3],
    )

    assert paragraph.has_embedding is True

    paragraph.embedding = []
    assert paragraph.has_embedding is False

    paragraph.embedding = None
    assert paragraph.has_embedding is False


def test_paragraph_preview_text_truncates_long_input():
    long_text = "a" * 150
    paragraph = Paragraph(
        id=2,
        expression_id=1,
        text=long_text,
        text_hash="hash2",
        position=0,
    )

    preview = paragraph.preview_text
    assert len(preview) == 103  # 100 chars + "..."
    assert preview.endswith("...")
