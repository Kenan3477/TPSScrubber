from app.parser import parse_number_file


CRM = b"""Contact ID,First Name,Last Name,Email,Company,Job Title,Address,City,Postcode,Mobile,Landline,Owner,Notes
1001,Jane,Smith,jane@acme.test,Acme,Director,1 High St,London,SW1A 1AA,7487723751,020 7946 0958,Sam,Call mornings
1002,John,Jones,john@acme.test,Acme,Manager,2 High St,Leeds,LS1 1BA,+447123456780,1912345678,Sam,OK
1003,Pat,Lee,pat@acme.test,Acme,Analyst,3 High St,London,E1 6AN,,n/a,Sam,No numbers
"""


def test_parses_plain_txt_list():
    parsed = parse_number_file("numbers.txt", b"07123456789\n+447123456780\nnot-a-number\n07123456789\n")
    assert [row.normalized for row in parsed.items] == [
        "07123456789",
        "07123456780",
        None,
        "07123456789",
    ]


def test_parses_csv_with_named_phone_column():
    parsed = parse_number_file("list.csv", b"name,phone,company\nJane,07123 456789,Acme\n")
    assert len(parsed.items) == 1
    assert parsed.items[0].normalized == "07123456789"
    assert parsed.items[0].fields["name"] == "Jane"
    assert parsed.items[0].fields["company"] == "Acme"
    assert parsed.items[0].fields["phone"] == "07123 456789"


def test_detects_mobile_and_landline_in_crm_export():
    parsed = parse_number_file("crm.csv", CRM)
    assert parsed.phone_fields == ["Mobile", "Landline"]
    assert parsed.source_rows == 3
    numbers = [(item.source_field, item.normalized) for item in parsed.items]
    assert ("Mobile", "07487723751") in numbers
    assert ("Landline", "02079460958") in numbers
    assert ("Mobile", "07123456780") in numbers
    assert ("Landline", "01912345678") in numbers
    jane = next(item for item in parsed.items if item.normalized == "07487723751")
    assert jane.fields["Email"] == "jane@acme.test"
    assert jane.fields["Postcode"] == "SW1A 1AA"
    assert jane.fields["Company"] == "Acme"
    assert jane.fields["Contact ID"] == "1001"
