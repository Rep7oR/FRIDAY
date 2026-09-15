from jarvis.core.tools.files import ListFilesTool, ReadFileTool, WriteFileTool


def test_write_then_read_round_trip():
    write = WriteFileTool()
    read = ReadFileTool()

    result = write.run(path="notes/todo.txt", content="buy milk")
    assert "Wrote" in result

    content = read.run(path="notes/todo.txt")
    assert content == "buy milk"


def test_list_files_shows_written_entries():
    WriteFileTool().run(path="a.txt", content="x")
    WriteFileTool().run(path="sub/b.txt", content="y")

    listing = ListFilesTool().run(path=".")
    assert "[file] a.txt" in listing
    assert "[dir] sub" in listing


def test_read_missing_file_reports_error():
    result = ReadFileTool().run(path="does_not_exist.txt")
    assert result.startswith("Error:")


def test_path_traversal_is_blocked():
    result = ReadFileTool().run(path="../../etc/passwd")
    assert "escapes the sandboxed workspace" in result

    result = WriteFileTool().run(path="../evil.txt", content="pwned")
    assert "escapes the sandboxed workspace" in result
