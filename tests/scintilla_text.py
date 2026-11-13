"""Read UTF-8 text from a Scintilla window through remote process memory."""


def read_editor_text(send, read_bytes, window, memory, capacity):
    # Formatting can replace the document between two window messages. Use the
    # allocated capacity, not a length queried before SCI_GETTEXT is dispatched.
    copied = send(window, 2182, capacity, memory)
    assert 0 <= copied < capacity - 1, 'Editor text filled the remote buffer; snapshot may be truncated'
    return read_bytes(copied + 1)[:copied].decode('utf-8')
