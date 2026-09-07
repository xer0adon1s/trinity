from __future__ import annotations

from trinity.methods import format_index, load_all, lookup


def test_lame_index_ships_with_citations():
    index = lookup("Lame")
    assert index is not None
    assert index.platform == "htb"
    assert len(index.methods) >= 2
    for method in index.methods:
        assert method.author
        assert method.source_url.startswith("http")
        assert len(method.summary) < 400


def test_format_index_renders_author_inline():
    text = format_index(lookup("Lame"))
    assert "0xdf" in text
    assert "https://0xdf.gitlab.io" in text
    assert "not a walkthrough" in text.lower() or "not the answer" in text.lower()


def test_unknown_box_is_none():
    assert lookup("DefinitelyNotABox") is None


def test_load_all_finds_yaml():
    assert any(i.box_name == "Lame" for i in load_all())
