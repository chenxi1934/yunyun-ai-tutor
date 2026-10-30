import pytest
from app.tools import Registry

HEADER = '--- example.py\n+++ example.py（草稿）\n'
NO_NEWLINE = '\\ No newline at end of file\n'


@pytest.mark.parametrize('before,after,expected', [
    ('print(1)', 'print(2)',
     '@@ -1 +1 @@\n-print(1)\n' + NO_NEWLINE + '+print(2)\n' + NO_NEWLINE),
    ('print(1)', 'print(2)\n',
     '@@ -1 +1 @@\n-print(1)\n' + NO_NEWLINE + '+print(2)\n'),
    ('print(1)\n', 'print(2)',
     '@@ -1 +1 @@\n-print(1)\n+print(2)\n' + NO_NEWLINE),
    ('', 'print(2)', '@@ -0,0 +1 @@\n+print(2)\n' + NO_NEWLINE),
    ('print(1)', '', '@@ -1 +0,0 @@\n-print(1)\n' + NO_NEWLINE),
    ('print(1)\n', 'print(2)\n', '@@ -1 +1 @@\n-print(1)\n+print(2)\n'),
    ('print(1)\r\n', 'print(2)\r\n', '@@ -1 +1 @@\n-print(1)\r\n+print(2)\r\n'),
    ('before\ntail', 'after\ntail', '@@ -1,2 +1,2 @@\n-before\n+after\n tail\n' + NO_NEWLINE),
], ids=['both-missing', 'old-missing', 'new-missing', 'create', 'delete', 'lf', 'crlf', 'context-missing'])
def test_unified_diff_keeps_lines_and_missing_newline_markers(before, after, expected):
    assert Registry._diff('example.py', before, after) == HEADER + expected


@pytest.mark.parametrize('content', ['', 'print(1)', 'print(1)\n', 'print(1)\r\n'])
def test_identical_content_has_no_diff(content):
    assert Registry._diff('example.py', content, content) == ''
