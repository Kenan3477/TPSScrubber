from app.parser import parse_number_file


def test_parses_plain_txt_list():
    content = b"07123456789\n+447123456780\nnot-a-number\n07123456789\n"
    rows = parse_number_file("numbers.txt", content)
    assert [row.normalized for row in rows] == [
        "07123456789",
        "07123456780",
        None,
        "07123456789",
    ]


def test_parses_csv_with_named_phone_column():
    content = b"name,phone,company\nJane,07123 456789,Acme\n"
    rows = parse_number_file("list.csv", content)
    assert len(rows) == 1
    assert rows[0].normalized == "07123456789"
    assert rows[0].extra["name"] == "Jane"
    assert rows[0].extra["company"] == "Acme"
