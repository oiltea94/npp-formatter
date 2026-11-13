"""Deterministic coverage of document replacement during smoke-test polling."""
import unittest

from scintilla_text import read_editor_text


class Editor:
    def __init__(self, before, after, capacity=128):
        self.document = before
        self.after = after
        self.memory = bytearray(b'X' * capacity)
        self.capacity = capacity

    def send(self, window, message, size, pointer):
        if message == 2006:  # SCI_GETLENGTH: replacement happens after the query.
            length = len(self.document)
            self.document = self.after
            return length
        if message == 2182:  # SCI_GETTEXT: copy the document at message dispatch.
            self.document = self.after
            assert 0 < size <= self.capacity
            copied = min(len(self.document), size - 1)
            self.memory[:copied + 1] = self.document[:copied] + b'\0'
            return copied
        raise AssertionError(f'Unexpected message: {message}')

    def read(self):
        return read_editor_text(self.send, lambda size: bytes(self.memory[:size]),
                                1, 2, self.capacity)


class ScintillaTextTests(unittest.TestCase):
    def test_growth_does_not_split_a_utf8_character(self):
        before = 'const emoji="😀";const answer=42; // 中文\n'.encode('utf-8')
        after = 'const emoji = "😀";\nconst answer = 42; // 中文\n'.encode('utf-8')
        self.assertEqual(Editor(before, after).read(), after.decode('utf-8'))

    def test_shrink_does_not_include_stale_bytes_or_terminator(self):
        self.assertEqual(Editor(b'x' * 100, '中'.encode('utf-8')).read(), '中')

    def test_empty_replacement(self):
        self.assertEqual(Editor(b'old text', b'').read(), '')

    def test_embedded_nul_is_preserved(self):
        self.assertEqual(Editor(b'a\0b', b'a\0b').read(), 'a\0b')

    def test_invalid_utf8_still_fails(self):
        with self.assertRaises(UnicodeDecodeError):
            Editor(b'\xff', b'\xff').read()

    def test_full_buffer_fails_explicitly_before_decoding(self):
        with self.assertRaisesRegex(AssertionError, 'buffer'):
            Editor(b'x' * 127, b'x' * 127).read()


if __name__ == '__main__':
    unittest.main()
