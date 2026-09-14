from agentify.markdown import lines_outside_fences


def test_lines_outside_fences_skips_fenced_blocks_and_keeps_numbers():
    result = lines_outside_fences("a\n```\nb\n```\nc\n")
    assert result == [(1, "a"), (5, "c")]


def test_unterminated_fence_swallows_the_rest():
    result = lines_outside_fences("a\n```\nb\n")
    assert result == [(1, "a")]
