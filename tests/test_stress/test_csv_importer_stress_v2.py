"""Second wave of CSV importer stress tests.

Goes beyond the existing stress tests with:
    - Encoding nightmares (Latin-1, CP1252, mixed)
    - Pathological delimiters (pipes, @ signs)
    - Injection payloads in cell values
    - State normalization adversarial inputs
    - Phone/email normalization edge cases
    - Name splitting chaos
    - Extremely wide files (hundreds of columns)
    - Binary garbage disguised as CSV
"""

from pathlib import Path

import pytest

from src.core.exceptions import ImportError_
from src.integrations.csv_importer import CSVImporter


# =========================================================================
# ENCODING NIGHTMARES
# =========================================================================


class TestEncodingNightmares:
    """Files with hostile encodings."""

    def test_latin1_encoded_file(self, tmp_path):
        """Latin-1 file with accented characters."""
        csv_file = tmp_path / "latin1.csv"
        csv_file.write_bytes(
            "Name,Email\nJosé,jose@test.com\nRené,rene@test.com\n".encode("latin-1")
        )
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.total_rows == 2

    def test_cp1252_smart_quotes(self, tmp_path):
        """Windows CP1252 with smart quotes (common Excel export)."""
        csv_file = tmp_path / "cp1252.csv"
        # \x93 and \x94 are left/right double quotes in CP1252
        csv_file.write_bytes(
            b"Name,Notes\nJohn,\x93Smart quotes\x94\n"
        )
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.total_rows == 1

    def test_mixed_encoding_survives(self, tmp_path):
        """File with mixed encoding (UTF-8 header, Latin-1 data)."""
        csv_file = tmp_path / "mixed.csv"
        header = "Name,Email\n".encode("utf-8")
        data = "François,franc@test.com\n".encode("latin-1")
        csv_file.write_bytes(header + data)
        importer = CSVImporter()
        # Should survive with one of the fallback encodings
        result = importer.parse_file(csv_file)
        assert result.total_rows >= 1

    def test_null_bytes_in_file(self, tmp_path):
        """File containing null bytes."""
        csv_file = tmp_path / "nulls.csv"
        csv_file.write_bytes(b"Name,Email\nJohn\x00,john@test.com\n")
        importer = CSVImporter()
        # Should either parse or raise ImportError_, not crash
        try:
            result = importer.parse_file(csv_file)
            assert isinstance(result.headers, list)
        except ImportError_:
            pass  # Acceptable to reject


# =========================================================================
# PATHOLOGICAL DELIMITERS
# =========================================================================


class TestPathologicalDelimiters:
    """Files where the sniffer might get confused."""

    def test_pipe_delimited(self, tmp_path):
        """Pipe-delimited file."""
        csv_file = tmp_path / "pipe.csv"
        csv_file.write_text("Name|Email\nJohn|john@test.com\n")
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert len(result.headers) == 2

    def test_email_at_sign_confuses_sniffer(self, tmp_path):
        """File with emails where @ might be detected as delimiter."""
        csv_file = tmp_path / "emails.csv"
        # Many emails might make sniffer think @ is a delimiter
        lines = ["Name,Email\n"]
        for i in range(20):
            lines.append(f"Person{i},person{i}@company.com\n")
        csv_file.write_text("".join(lines))
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        # Should correctly use comma, not @
        assert "Name" in result.headers
        assert "Email" in result.headers

    def test_single_column_file(self, tmp_path):
        """File with only one column (no delimiter at all)."""
        csv_file = tmp_path / "single.csv"
        csv_file.write_text("Name\nJohn\nJane\n")
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert len(result.headers) == 1
        assert result.total_rows == 2


# =========================================================================
# INJECTION PAYLOADS IN CELLS
# =========================================================================


class TestCellInjection:
    """CSV formula injection and other hostile cell values."""

    def test_formula_injection_in_name(self, tmp_path):
        """Excel formula injection (=CMD) should be stored as-is."""
        csv_file = tmp_path / "formula.csv"
        csv_file.write_text('Name,Email\n"=CMD(""calc"")",j@t.com\n')
        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        # The formula should be stored as a string, not executed
        assert records[0].first_name.startswith("=CMD")

    def test_html_injection_in_notes(self, tmp_path):
        """HTML/XSS payload should be stored as-is."""
        csv_file = tmp_path / "xss.csv"
        csv_file.write_text(
            'Name,Notes\nJohn,"<script>alert(1)</script>"\n'
        )
        importer = CSVImporter()
        mapping = {"first_name": "Name", "notes": "Notes"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert "<script>" in records[0].notes

    def test_sql_injection_in_company(self, tmp_path):
        """SQL injection in company name should be stored as-is."""
        csv_file = tmp_path / "sqli.csv"
        csv_file.write_text(
            "Name,Company\nJohn,\"'; DROP TABLE companies; --\"\n"
        )
        importer = CSVImporter()
        mapping = {"first_name": "Name", "company_name": "Company"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert "DROP TABLE" in records[0].company_name


# =========================================================================
# STATE NORMALIZATION ADVERSARIAL
# =========================================================================


class TestStateNormalizationAdversarial:
    """Push normalize_state to breaking point."""

    def test_empty_state(self):
        # Empty string -> .upper().strip() -> "" -> len <= 2 -> return ""
        assert CSVImporter.normalize_state("") == ""

    def test_whitespace_state(self):
        result = CSVImporter.normalize_state("  ")
        assert result == ""

    def test_three_char_gibberish(self):
        """Unknown 3+ char state gets truncated to first 2 chars."""
        result = CSVImporter.normalize_state("XYZ")
        assert result == "XY"  # Truncated, not valid

    def test_numeric_state(self):
        result = CSVImporter.normalize_state("123")
        assert result == "12"  # Truncated

    def test_special_chars_state(self):
        result = CSVImporter.normalize_state("!@#")
        assert len(result) == 2

    def test_all_50_state_names(self):
        """Every full state name should map correctly."""
        from src.integrations.csv_importer import _STATE_NAMES
        for full_name, code in _STATE_NAMES.items():
            result = CSVImporter.normalize_state(full_name)
            assert result == code, f"'{full_name}' -> '{result}', expected '{code}'"

    def test_lowercase_state_name(self):
        """Lowercase state name should work (.upper() is called)."""
        assert CSVImporter.normalize_state("texas") == "TX"

    def test_mixed_case_state_name(self):
        assert CSVImporter.normalize_state("Texas") == "TX"

    def test_state_with_extra_spaces(self):
        assert CSVImporter.normalize_state("  TX  ") == "TX"


# =========================================================================
# NAME SPLITTING CHAOS
# =========================================================================


class TestNameSplittingChaos:
    """Push split_full_name beyond reason."""

    def test_simple_name(self):
        assert CSVImporter.split_full_name("John Smith") == ("John", "Smith")

    def test_three_part_name(self):
        assert CSVImporter.split_full_name("Mary Jane Watson") == ("Mary", "Jane Watson")

    def test_single_name(self):
        assert CSVImporter.split_full_name("Cher") == ("Cher", "")

    def test_empty_string(self):
        assert CSVImporter.split_full_name("") == ("", "")

    def test_only_spaces(self):
        """Spaces only should split to empty parts."""
        assert CSVImporter.split_full_name("   ") == ("", "")

    def test_tab_separated_name(self):
        """Tab between parts should work (split on any whitespace)."""
        assert CSVImporter.split_full_name("John\tSmith") == ("John", "Smith")

    def test_multiple_spaces(self):
        """Multiple spaces between parts."""
        assert CSVImporter.split_full_name("John    Smith") == ("John", "Smith")

    def test_unicode_name(self):
        assert CSVImporter.split_full_name("José García") == ("José", "García")

    def test_name_with_suffix(self):
        assert CSVImporter.split_full_name("John Smith III") == ("John", "Smith III")

    def test_name_with_prefix(self):
        assert CSVImporter.split_full_name("Dr. John Smith") == ("Dr.", "John Smith")

    def test_hyphenated_last_name(self):
        assert CSVImporter.split_full_name("Mary Smith-Jones") == ("Mary", "Smith-Jones")

    def test_very_long_name(self):
        long_name = "A" * 5000 + " " + "B" * 5000
        first, last = CSVImporter.split_full_name(long_name)
        assert len(first) == 5000
        assert len(last) == 5000


# =========================================================================
# PHONE NORMALIZATION
# =========================================================================


class TestPhoneNormalization:
    """Phone normalization edge cases."""

    def test_normal_phone(self):
        assert CSVImporter.normalize_phone("(713) 555-1234") == "7135551234"

    def test_already_digits(self):
        assert CSVImporter.normalize_phone("7135551234") == "7135551234"

    def test_empty_string(self):
        assert CSVImporter.normalize_phone("") == ""

    def test_no_digits(self):
        assert CSVImporter.normalize_phone("no digits here") == ""

    def test_international_format(self):
        assert CSVImporter.normalize_phone("+1 (713) 555-1234") == "17135551234"

    def test_dots_as_separator(self):
        assert CSVImporter.normalize_phone("713.555.1234") == "7135551234"

    def test_spaces_only(self):
        assert CSVImporter.normalize_phone("   ") == ""


# =========================================================================
# EMAIL NORMALIZATION
# =========================================================================


class TestEmailNormalization:
    """Email normalization edge cases."""

    def test_uppercase_email(self):
        assert CSVImporter.normalize_email("JOHN@ACME.COM") == "john@acme.com"

    def test_mixed_case_email(self):
        assert CSVImporter.normalize_email("John.Doe@Acme.Com") == "john.doe@acme.com"

    def test_already_lowercase(self):
        assert CSVImporter.normalize_email("john@acme.com") == "john@acme.com"

    def test_email_with_spaces(self):
        assert CSVImporter.normalize_email("  john@acme.com  ") == "john@acme.com"

    def test_empty_email(self):
        assert CSVImporter.normalize_email("") == ""

    def test_not_really_an_email(self):
        """Garbage input should still be lowercased."""
        assert CSVImporter.normalize_email("NOT AN EMAIL") == "not an email"


# =========================================================================
# EXTREMELY WIDE FILES
# =========================================================================


class TestWideFiles:
    """Files with many columns."""

    def test_100_columns(self, tmp_path):
        """File with 100 columns."""
        headers = ",".join(f"Col{i}" for i in range(100))
        values = ",".join(f"val{i}" for i in range(100))
        csv_file = tmp_path / "wide.csv"
        csv_file.write_text(f"{headers}\n{values}\n")
        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert len(result.headers) == 100

    def test_mapping_with_wide_file(self, tmp_path):
        """Mapping should work on wide files, ignoring extra columns."""
        headers = ",".join(f"Col{i}" for i in range(100))
        values = ",".join(f"val{i}" for i in range(100))
        csv_file = tmp_path / "wide.csv"
        csv_file.write_text(f"{headers}\n{values}\n")
        importer = CSVImporter()
        mapping = {"first_name": "Col0", "email": "Col1"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "val0"


# =========================================================================
# BINARY GARBAGE
# =========================================================================


class TestBinaryGarbage:
    """Files that aren't really CSVs at all."""

    def test_binary_file(self, tmp_path):
        """Pure binary data should fail gracefully."""
        csv_file = tmp_path / "binary.csv"
        csv_file.write_bytes(bytes(range(256)))
        importer = CSVImporter()
        try:
            result = importer.parse_file(csv_file)
            # If it doesn't crash, that's fine
            assert isinstance(result.headers, list)
        except ImportError_:
            pass  # Also acceptable

    def test_pdf_disguised_as_csv(self, tmp_path):
        """PDF magic bytes disguised as CSV."""
        csv_file = tmp_path / "fake.csv"
        csv_file.write_bytes(b"%PDF-1.4 fake pdf content " + b"\x00" * 100)
        importer = CSVImporter()
        try:
            result = importer.parse_file(csv_file)
            assert isinstance(result.headers, list)
        except ImportError_:
            pass

    def test_gzip_disguised_as_csv(self, tmp_path):
        """Gzip magic bytes disguised as CSV."""
        csv_file = tmp_path / "fake.csv"
        csv_file.write_bytes(b"\x1f\x8b\x08" + b"\x00" * 100)
        importer = CSVImporter()
        try:
            result = importer.parse_file(csv_file)
            assert isinstance(result.headers, list)
        except ImportError_:
            pass
