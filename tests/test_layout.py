import layout


def L(top, x0, x1, text, size=9.0):
    return {"top": top, "x0": x0, "x1": x1, "text": text, "size": size}


FULL = "• Built contribution pages and pricing feeds for clients in London, Switzerland and"


def test_short_wrapped_last_line_is_an_orphan():
    out = layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 58, 140, "Emerging Markets.")], right_edge=545)
    assert len(out) == 1 and "Emerging Markets." in out[0]


def test_next_bullet_is_not_an_orphan():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 50, 120, "• Led x")], right_edge=545) == []


def test_heading_after_a_gap_is_not_an_orphan():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(125, 50, 90, "SKILLS")], right_edge=545) == []


def test_three_word_tail_is_fine():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 58, 200, "and Emerging Markets.")], right_edge=545) == []


def test_line_that_did_not_reach_the_edge_does_not_wrap():
    assert layout.find_orphans([L(100, 50, 300, "Short line"), L(112.5, 58, 100, "Two words")], right_edge=545) == []
