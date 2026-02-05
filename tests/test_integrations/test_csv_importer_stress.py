"""Hostile stress tests for CSV importer.

These tests attack edge cases, malformed input, and implicit assumptions
in CSVImporter to shake out bugs before phase 6.
"""

from pathlib import Path

import pytest

from src.integrations.csv_importer import CSVImporter


# =========================================================================
# UTF-8 BOM -- extremely common in files exported from Excel on Windows.
# The BOM bytes (\xef\xbb\xbf) will silently corrupt the first header
# unless the parser strips them.
# =========================================================================


class TestBOM:
    """Files exported from Excel on Windows often start with a UTF-8 BOM."""

    def test_utf8_bom_does_not_corrupt_first_header(self, tmp_path: Path):
        """A UTF-8 BOM must not appear inside the first header name."""
        csv_file = tmp_path / "bom.csv"
        # BOM + normal CSV
        csv_file.write_bytes(b"\xef\xbb\xbfName,Email\nJohn,j@test.com\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        # The header must be clean "Name", not "\ufeffName"
        assert result.headers[0] == "Name", (
            f"BOM leaked into first header: {result.headers[0]!r}"
        )

    def test_utf8_bom_mapping_still_works(self, tmp_path: Path):
        """Column mapping must work even when the file has a BOM."""
        csv_file = tmp_path / "bom.csv"
        csv_file.write_bytes(b"\xef\xbb\xbfName,Email\nJohn,j@test.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1, "BOM prevented mapping from matching headers"
        assert records[0].first_name == "John"


# =========================================================================
# DUPLICATE HEADERS -- real-world exports sometimes have two columns with
# the same name.  header_idx = {h: i ...} will silently shadow the first.
# =========================================================================


class TestDuplicateHeaders:
    """What happens when two columns share a name."""

    def test_duplicate_header_uses_first_column(self, tmp_path: Path):
        """With duplicate headers, the FIRST column wins in header_idx."""
        csv_file = tmp_path / "dup.csv"
        # Two "Name" columns -- first has the real name, second is empty
        csv_file.write_text("Name,Email,Name\nJohn,j@test.com,\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        # First "Name" column (index 0) has "John" and wins.
        assert len(records) == 1
        assert records[0].first_name == "John"


# =========================================================================
# RAGGED ROWS -- real CSVs often have rows shorter or longer than headers.
# =========================================================================


class TestRaggedRows:
    """Rows with more or fewer columns than the header row."""

    def test_short_row_does_not_crash(self, tmp_path: Path):
        """A row with fewer cells than headers must not blow up."""
        csv_file = tmp_path / "short.csv"
        # Header has 3 cols, data row has only 1
        csv_file.write_text("Name,Email,Phone\nJohn\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email", "phone": "Phone"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].email is None
        assert records[0].phone is None

    def test_extra_columns_ignored(self, tmp_path: Path):
        """Rows with MORE columns than headers are handled gracefully."""
        csv_file = tmp_path / "wide.csv"
        csv_file.write_text("Name,Email\nJohn,j@t.com,bonus1,bonus2\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"


# =========================================================================
# EMPTY / DEGENERATE FILES
# =========================================================================


class TestDegenerateFiles:
    """Completely empty files, files with only whitespace, etc."""

    def test_zero_byte_file(self, tmp_path: Path):
        """A 0-byte file should raise ImportError_, not crash."""
        from src.core.exceptions import ImportError_

        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        importer = CSVImporter()
        with pytest.raises(ImportError_):
            importer.parse_file(csv_file)

    def test_newlines_only(self, tmp_path: Path):
        """A file with only blank lines should raise ImportError_."""
        from src.core.exceptions import ImportError_

        csv_file = tmp_path / "blanks.csv"
        csv_file.write_text("\n\n\n\n")

        importer = CSVImporter()
        with pytest.raises(ImportError_):
            importer.parse_file(csv_file)

    def test_apply_mapping_on_empty_data(self, tmp_path: Path):
        """apply_mapping on a headers-only file returns empty list."""
        csv_file = tmp_path / "headonly.csv"
        csv_file.write_text("Name,Email\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records == []


# =========================================================================
# QUOTED FIELDS -- the bread and butter of CSV hell.
# =========================================================================


class TestQuotedFields:
    """Fields with embedded commas, newlines, and quotes."""

    def test_comma_inside_quoted_field(self, tmp_path: Path):
        """A comma inside quotes is part of the value, not a delimiter."""
        csv_file = tmp_path / "quoted.csv"
        csv_file.write_text('Name,Company\nJohn,"Acme, Inc."\n')

        importer = CSVImporter()
        mapping = {"first_name": "Name", "company_name": "Company"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].company_name == "Acme, Inc."

    def test_escaped_quotes_inside_field(self, tmp_path: Path):
        """Doubled quotes inside a quoted field are a single quote."""
        csv_file = tmp_path / "escaped.csv"
        csv_file.write_text('Name,Notes\nJohn,"Said ""hello"" to me"\n')

        importer = CSVImporter()
        mapping = {"first_name": "Name", "notes": "Notes"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].notes == 'Said "hello" to me'

    def test_newline_inside_quoted_field(self, tmp_path: Path):
        """A newline inside a quoted field should NOT split the row."""
        csv_file = tmp_path / "multiline.csv"
        csv_file.write_text('Name,Notes\nJohn,"line1\nline2"\nJane,ok\n')

        importer = CSVImporter()
        mapping = {"first_name": "Name", "notes": "Notes"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 2
        assert records[0].notes == "line1\nline2"
        assert records[1].first_name == "Jane"


# =========================================================================
# WHITESPACE-HEAVY ROWS -- rows that LOOK empty but aren't truly empty.
# =========================================================================


class TestWhitespaceRows:
    """Rows filled with spaces, tabs, or mixed whitespace."""

    def test_spaces_only_row_is_skipped(self, tmp_path: Path):
        """A row of only spaces should be treated as empty."""
        csv_file = tmp_path / "spaces.csv"
        csv_file.write_text("Name,Email\nJohn,j@t.com\n   ,   \nJane,jane@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 2

    def test_tabs_only_row_is_skipped(self, tmp_path: Path):
        """A row of only tabs should be treated as empty."""
        csv_file = tmp_path / "tabs.csv"
        csv_file.write_text("Name,Email\nJohn,j@t.com\n\t,\t\nJane,jane@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 2

    def test_multiple_consecutive_empty_rows(self, tmp_path: Path):
        """Multiple empty rows in a row should all be skipped."""
        csv_file = tmp_path / "multi_empty.csv"
        csv_file.write_text("Name,Email\n,,\n,,\n,,\nJohn,j@t.com\n,,\n,,\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"


# =========================================================================
# PARTIAL / HALF-EMPTY ROWS -- one cell populated, the rest blank.
# These should NOT be treated as empty rows -- they have data.
# =========================================================================


class TestPartialRows:
    """Rows with some empty and some populated cells."""

    def test_email_only_no_name_is_excluded(self, tmp_path: Path):
        """A row with email but no name passes empty-row check but is
        excluded by the 'at least a name' filter."""
        csv_file = tmp_path / "emailonly.csv"
        csv_file.write_text("Name,Email\n,j@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 0

    def test_name_only_no_email_is_included(self, tmp_path: Path):
        """A row with a name but no email IS included."""
        csv_file = tmp_path / "nameonly.csv"
        csv_file.write_text("Name,Email\nJohn,\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].email is None


# =========================================================================
# TOTAL_ROWS CONSISTENCY -- parse_file counts ALL rows including empties,
# but apply_mapping skips empties.  These numbers will diverge.
# =========================================================================


class TestTotalRowsConsistency:
    """parse_file.total_rows vs apply_mapping record count."""

    def test_total_rows_excludes_empty_rows(self, tmp_path: Path):
        """parse_file total_rows and apply_mapping both exclude empties."""
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text("Name,Email\nJohn,j@t.com\n,,\nJane,jane@t.com\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)

        # Empty rows are filtered at the parse level -- counts are consistent.
        assert result.total_rows == 2
        assert len(records) == 2


# =========================================================================
# TAB-DELIMITED AND SEMICOLON-DELIMITED FILES
# Real-world files aren't always comma-separated.
# =========================================================================


class TestAlternateDelimiters:
    """Non-comma delimiters that should work via the sniffer."""

    def test_tab_delimited(self, tmp_path: Path):
        """Tab-delimited files should parse correctly."""
        csv_file = tmp_path / "tabs.csv"
        csv_file.write_text("Name\tEmail\nJohn\tj@t.com\nJane\tjane@t.com\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        # The sniffer should detect tab; if it fails, default reader
        # uses comma and this will be 1 column with tab-joined text.
        assert len(result.headers) == 2, (
            f"Tab-delimited file parsed as {len(result.headers)} column(s): {result.headers}"
        )
        assert result.total_rows == 2

    def test_semicolon_delimited(self, tmp_path: Path):
        """Semicolon-delimited files (common in European locales)."""
        csv_file = tmp_path / "semi.csv"
        csv_file.write_text("Name;Email\nJohn;j@t.com\nJane;jane@t.com\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert len(result.headers) == 2, (
            f"Semicolon-delimited file parsed as {len(result.headers)} column(s): {result.headers}"
        )

    def test_tab_delimited_apply_mapping(self, tmp_path: Path):
        """apply_mapping should work on tab-delimited files."""
        csv_file = tmp_path / "tabs.csv"
        csv_file.write_text("Name\tEmail\nJohn\tj@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"


# =========================================================================
# STATE NORMALIZATION EDGE CASES
# =========================================================================


class TestStateEdgeCases:
    """State field gets .upper().strip()[:2] -- what are the edge cases?"""

    def test_full_state_name_truncated_to_2(self, tmp_path: Path):
        """'California' becomes 'CA' -- wait, it becomes 'CA'... right?"""
        csv_file = tmp_path / "state.csv"
        csv_file.write_text("Name,State\nJohn,California\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "state": "State"}
        records = importer.apply_mapping(csv_file, mapping)
        # .upper().strip()[:2] on "California" = "CA" -- this coincidentally
        # works for California but NOT for most states.
        assert records[0].state == "CA"

    def test_state_texas_becomes_TX(self, tmp_path: Path):
        """'texas' is resolved to 'TX' via state name lookup."""
        csv_file = tmp_path / "state.csv"
        csv_file.write_text("Name,State\nJohn,texas\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "state": "State"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].state == "TX"

    def test_single_char_state(self, tmp_path: Path):
        """A single character state like 'T' survives truncation."""
        csv_file = tmp_path / "state.csv"
        csv_file.write_text("Name,State\nJohn,T\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "state": "State"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].state == "T"


# =========================================================================
# PRESET DETECTION AMBIGUITY -- can a file match BOTH presets?
# =========================================================================


class TestPresetAmbiguity:
    """What happens when headers partially match multiple presets?"""

    def test_shared_columns_first_preset_wins(self):
        """Headers matching both presets -- dict iteration order determines winner."""
        # "Email" matches phoneburner, "State" matches both,
        # "Phone" matches phoneburner (as "Phone") and aapl (as "Phone Number")
        # but "Phone" != "Phone Number" so it only matches phoneburner.
        headers = ["Email", "State", "Phone", "Organization", "Contact Name"]
        importer = CSVImporter()
        result = importer.detect_preset(headers)
        # Both presets have "State". AAPL has Organization + Contact Name + State = 3/5 = 60%.
        # PhoneBurner has Email + Phone + State = 3/7 = 43% (below 60%).
        # So AAPL should win.
        assert result == "aapl"


# =========================================================================
# UNICODE AND SPECIAL CHARACTER STRESS
# =========================================================================


class TestUnicodeStress:
    """Non-ASCII names, emails, and other fields."""

    def test_unicode_names(self, tmp_path: Path):
        """Names with accented characters, CJK, emoji, etc."""
        csv_file = tmp_path / "unicode.csv"
        csv_file.write_text("Name,Email\nJosé,jose@t.com\n田中太郎,tanaka@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 2
        assert records[0].first_name == "José"
        assert records[1].first_name == "田中太郎"

    def test_header_with_unicode(self, tmp_path: Path):
        """Headers containing unicode characters."""
        csv_file = tmp_path / "uheader.csv"
        csv_file.write_text("Prénom,Courriel\nJean,jean@t.com\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.headers == ["Prénom", "Courriel"]


# =========================================================================
# LARGE-ISH FILE BEHAVIOR (not truly huge, but enough to matter)
# =========================================================================


class TestLargerFiles:
    """Moderately sized files to test performance and correctness at scale."""

    def test_1000_rows(self, tmp_path: Path):
        """1000 rows should all be processed correctly."""
        lines = ["Name,Email\n"]
        for i in range(1000):
            lines.append(f"Person{i},person{i}@test.com\n")
        csv_file = tmp_path / "big.csv"
        csv_file.write_text("".join(lines))

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1000

    def test_1000_rows_with_scattered_empties(self, tmp_path: Path):
        """1000 rows with every 10th row empty."""
        lines = ["Name,Email\n"]
        expected_count = 0
        for i in range(1000):
            if i % 10 == 0:
                lines.append(",,\n")
            else:
                lines.append(f"Person{i},person{i}@test.com\n")
                expected_count += 1
        csv_file = tmp_path / "scattered.csv"
        csv_file.write_text("".join(lines))

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == expected_count


# =========================================================================
# apply_mapping WITH NON-CSV EXTENSION -- the else branch treats ANY
# non-xlsx file as CSV.  This is inconsistent with parse_file which rejects
# unknown extensions.
# =========================================================================


class TestExtensionConsistency:
    """Both parse_file and apply_mapping reject unsupported extensions."""

    def test_parse_file_rejects_txt(self, tmp_path: Path):
        """parse_file raises on .txt extension."""
        from src.core.exceptions import ImportError_

        txt_file = tmp_path / "data.txt"
        txt_file.write_text("Name,Email\nJohn,j@t.com\n")

        importer = CSVImporter()
        with pytest.raises(ImportError_, match="Unsupported file type"):
            importer.parse_file(txt_file)

    def test_apply_mapping_rejects_txt(self, tmp_path: Path):
        """apply_mapping also raises on .txt extension."""
        from src.core.exceptions import ImportError_

        txt_file = tmp_path / "data.txt"
        txt_file.write_text("Name,Email\nJohn,j@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        with pytest.raises(ImportError_, match="Unsupported file type"):
            importer.apply_mapping(txt_file, mapping)


# =========================================================================
# MAPPING TO UNKNOWN FIELD NAMES
# =========================================================================


class TestUnknownFieldMapping:
    """What if the mapping dict has a field_name that isn't handled?"""

    def test_unknown_field_name_silently_ignored(self, tmp_path: Path):
        """A mapping like {'favorite_color': 'Color'} is just ignored."""
        csv_file = tmp_path / "extra.csv"
        csv_file.write_text("Name,Color\nJohn,Blue\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "favorite_color": "Color"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"
        # "favorite_color" doesn't match any elif branch, so it's silently dropped.
        # The record doesn't have a favorite_color attribute.
        assert not hasattr(records[0], "favorite_color")


# =========================================================================
# PRESET + EXPLICIT MAPPING INTERACTION
# =========================================================================


class TestPresetMappingInteraction:
    """What happens when both preset and mapping are provided?"""

    def test_preset_ignored_when_mapping_provided(self, tmp_path: Path):
        """If mapping is non-empty, preset should not override it."""
        csv_file = tmp_path / "pb.csv"
        csv_file.write_text(
            "First Name,Last Name,Email,Phone,Company,Title,State\n"
            "John,Doe,john@acme.com,5551234567,Acme Corp,VP Sales,TX\n"
        )
        importer = CSVImporter()
        # Provide explicit mapping that only maps first_name
        mapping = {"first_name": "First Name"}
        records = importer.apply_mapping(csv_file, mapping, preset="phoneburner")
        assert len(records) == 1
        assert records[0].first_name == "John"
        # Preset should NOT have filled in email, etc. because mapping was non-empty
        assert records[0].email is None
