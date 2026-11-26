def test_releasing_a_files_pages_keeps_its_contents(tmp_path):
    from games.api.http import release_pages

    path = tmp_path / "bundle"
    with open(path, "wb") as file:
        file.write(b"abc" * 1000)
        release_pages(file)
        file.write(b"def")
    assert path.read_bytes() == b"abc" * 1000 + b"def"
