"""Tests for CSV/XLSX importer."""

from pathlib import Path

import pytest

from src.integrations.csv_importer import PRESETS, CSVImporter, ParseResult

# =========================================================================
# CSV PARSING TESTS
# =========================================================================


class TestParseCSV:
    """Test CSV file parsing."""

    def test_parse_basic_csv(self, tmp_path: Path):
        """Parse a simple CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "First Name,Last Name,Email\n" "John,Doe,john@test.com\n" "Jane,Smith,jane@test.com\n"
        )
        importer = CSVImporter()
        result = importer.parse_file(csv_file)

        assert result.headers == ["First Name", "Last Name", "Email"]
        assert result.total_rows == 2
        assert len(result.sample_rows) == 2
        assert result.sample_rows[0] == ["John", "Doe", "john@test.com"]

    def test_parse_returns_sample_max_5(self, tmp_path: Path):
        """Sample rows capped at 5."""
        lines = ["Name\n"] + [f"Person{i}\n" for i in range(20)]
        csv_file = tmp_path / "big.csv"
        csv_file.write_text("".join(lines))

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert len(result.sample_rows) == 5
        assert result.total_rows == 20

    def test_parse_empty_data_rows(self, tmp_path: Path):
        """CSV with headers only returns 0 total_rows."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("Name,Email\n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.total_rows == 0
        assert result.headers == ["Name", "Email"]

    def test_parse_nonexistent_file(self):
        """Raises ImportError_ for missing file."""
        from src.core.exceptions import ImportError_

        importer = CSVImporter()
        with pytest.raises(ImportError_, match="File not found"):
            importer.parse_file(Path("/nonexistent/file.csv"))

    def test_parse_unsupported_extension(self, tmp_path: Path):
        """Raises ImportError_ for unknown file type."""
        from src.core.exceptions import ImportError_

        bad_file = tmp_path / "test.pdf"
        bad_file.write_text("not a csv")

        importer = CSVImporter()
        with pytest.raises(ImportError_, match="Unsupported file type"):
            importer.parse_file(bad_file)

    def test_parse_csv_with_whitespace(self, tmp_path: Path):
        """Headers and values are stripped of whitespace."""
        csv_file = tmp_path / "whitespace.csv"
        csv_file.write_text("  Name  , Email  \n  John  , john@test.com  \n")

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.headers == ["Name", "Email"]
        assert result.sample_rows[0] == ["John", "john@test.com"]

    def test_parse_csv_latin1(self, tmp_path: Path):
        """Handles Latin-1 encoded files."""
        csv_file = tmp_path / "latin.csv"
        csv_file.write_bytes("Name,City\nJos\xe9,S\xe3o Paulo\n".encode("latin-1"))

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.total_rows == 1
        assert result.encoding == "latin-1"


# =========================================================================
# PRESET DETECTION TESTS
# =========================================================================


class TestPresetDetection:
    """Test preset format detection from headers."""

    def test_detect_phoneburner(self):
        """Detects PhoneBurner format."""
        headers = ["First Name", "Last Name", "Email", "Phone", "Company", "Title", "State"]
        importer = CSVImporter()
        assert importer.detect_preset(headers) == "phoneburner"

    def test_detect_aapl(self):
        """Detects AAPL format."""
        headers = ["Contact Name", "Email Address", "Phone Number", "Organization", "State"]
        importer = CSVImporter()
        assert importer.detect_preset(headers) == "aapl"

    def test_detect_phoneburner_partial(self):
        """Detects PhoneBurner with partial headers (>60% match)."""
        # 5 of 7 fields = ~71%
        headers = ["First Name", "Last Name", "Email", "Phone", "Company"]
        importer = CSVImporter()
        assert importer.detect_preset(headers) == "phoneburner"

    def test_detect_unknown_format(self):
        """Returns None for unrecognized format."""
        headers = ["col_a", "col_b", "col_c"]
        importer = CSVImporter()
        assert importer.detect_preset(headers) is None

    def test_detect_case_insensitive(self):
        """Detection is case-insensitive."""
        headers = ["first name", "last name", "email", "phone", "company", "title", "state"]
        importer = CSVImporter()
        assert importer.detect_preset(headers) == "phoneburner"

    def test_parse_file_includes_detected_preset(self, tmp_path: Path):
        """parse_file result includes detected preset."""
        csv_file = tmp_path / "pb.csv"
        csv_file.write_text(
            "First Name,Last Name,Email,Phone,Company,Title,State\nJohn,Doe,j@t.com,555,Acme,VP,TX\n"
        )

        importer = CSVImporter()
        result = importer.parse_file(csv_file)
        assert result.detected_preset == "phoneburner"


# =========================================================================
# COLUMN MAPPING TESTS
# =========================================================================


class TestApplyMapping:
    """Test column mapping to ImportRecord."""

    def test_basic_mapping(self, tmp_path: Path):
        """Apply explicit column mapping."""
        csv_file = tmp_path / "mapped.csv"
        csv_file.write_text("fn,ln,em,ph,co\n" "John,Doe,john@test.com,5551234567,Acme Corp\n")
        importer = CSVImporter()
        mapping = {
            "first_name": "fn",
            "last_name": "ln",
            "email": "em",
            "phone": "ph",
            "company_name": "co",
        }
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].last_name == "Doe"
        assert records[0].email == "john@test.com"
        assert records[0].phone == "5551234567"
        assert records[0].company_name == "Acme Corp"

    def test_email_normalized_to_lowercase(self, tmp_path: Path):
        """Email is lowercased during mapping."""
        csv_file = tmp_path / "email.csv"
        csv_file.write_text("Name,Email\nJohn,JOHN@TEST.COM\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].email == "john@test.com"

    def test_phone_normalized_to_digits(self, tmp_path: Path):
        """Phone is stripped to digits during mapping."""
        csv_file = tmp_path / "phone.csv"
        csv_file.write_text("Name,Phone\nJohn,(713) 555-1234\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "phone": "Phone"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].phone == "7135551234"

    def test_state_uppercased_and_trimmed(self, tmp_path: Path):
        """State is uppercased and trimmed to 2 chars."""
        csv_file = tmp_path / "state.csv"
        csv_file.write_text("Name,State\nJohn, texas \n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "state": "State"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].state == "TE"

    def test_skip_empty_rows(self, tmp_path: Path):
        """Empty rows are skipped."""
        csv_file = tmp_path / "gaps.csv"
        csv_file.write_text("Name,Email\nJohn,j@t.com\n,,\nJane,jane@t.com\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "Email"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 2

    def test_skip_records_without_name(self, tmp_path: Path):
        """Records with no name are excluded."""
        csv_file = tmp_path / "noname.csv"
        csv_file.write_text("Email,Phone\njohn@t.com,555\n")

        importer = CSVImporter()
        mapping = {"email": "Email", "phone": "Phone"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 0

    def test_preset_based_mapping(self, tmp_path: Path):
        """Use preset to auto-generate mapping."""
        csv_file = tmp_path / "pb.csv"
        csv_file.write_text(
            "First Name,Last Name,Email,Phone,Company,Title,State\n"
            "John,Doe,john@acme.com,5551234567,Acme Corp,VP Sales,TX\n"
        )
        importer = CSVImporter()
        records = importer.apply_mapping(csv_file, {}, preset="phoneburner")
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].last_name == "Doe"
        assert records[0].email == "john@acme.com"
        assert records[0].company_name == "Acme Corp"
        assert records[0].title == "VP Sales"

    def test_aapl_preset_splits_name(self, tmp_path: Path):
        """AAPL preset splits 'Contact Name' into first/last."""
        csv_file = tmp_path / "aapl.csv"
        csv_file.write_text(
            "Contact Name,Email Address,Phone Number,Organization,State\n"
            "John Doe,john@org.com,5551234567,Big Org,TX\n"
        )
        importer = CSVImporter()
        records = importer.apply_mapping(csv_file, {}, preset="aapl")
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].last_name == "Doe"

    def test_mapping_with_missing_column(self, tmp_path: Path):
        """Mapping referencing nonexistent column is silently skipped."""
        csv_file = tmp_path / "missing.csv"
        csv_file.write_text("Name\nJohn\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "email": "NonExistentColumn"}
        records = importer.apply_mapping(csv_file, mapping)
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].email is None

    def test_notes_and_source_mapping(self, tmp_path: Path):
        """Notes and source fields are mapped correctly."""
        csv_file = tmp_path / "extra.csv"
        csv_file.write_text("Name,Notes,Source\nJohn,Hot lead,LinkedIn\n")

        importer = CSVImporter()
        mapping = {"first_name": "Name", "notes": "Notes", "source": "Source"}
        records = importer.apply_mapping(csv_file, mapping)
        assert records[0].notes == "Hot lead"
        assert records[0].source == "LinkedIn"


# =========================================================================
# NAME SPLITTING TESTS
# =========================================================================


class TestNameSplitting:
    """Test name splitting utilities."""

    def test_split_full_name(self):
        """Splits full name into first/last."""
        first, last = CSVImporter.split_full_name("John Doe")
        assert first == "John"
        assert last == "Doe"

    def test_split_name_with_middle(self):
        """Handles middle name (last = rest after first)."""
        first, last = CSVImporter.split_full_name("John Michael Doe")
        assert first == "John"
        assert last == "Michael Doe"

    def test_split_single_name(self):
        """Handles single name."""
        first, last = CSVImporter.split_full_name("Madonna")
        assert first == "Madonna"
        assert last == ""

    def test_split_empty_name(self):
        """Handles empty string."""
        first, last = CSVImporter.split_full_name("")
        assert first == ""
        assert last == ""

    def test_split_whitespace_name(self):
        """Handles whitespace-only string."""
        first, last = CSVImporter.split_full_name("   ")
        assert first == ""
        assert last == ""


# =========================================================================
# EMAIL NORMALIZATION TESTS
# =========================================================================


class TestEmailNormalization:
    """Test email normalization."""

    def test_lowercase_email(self):
        """Email is lowercased."""
        assert CSVImporter.normalize_email("John@Test.COM") == "john@test.com"

    def test_strip_whitespace(self):
        """Whitespace is stripped."""
        assert CSVImporter.normalize_email("  john@test.com  ") == "john@test.com"

    def test_normalizes_any_string(self):
        """Normalize just lowercases and strips (validation separate)."""
        assert CSVImporter.normalize_email("not-an-email") == "not-an-email"
        assert CSVImporter.normalize_email("") == ""


# =========================================================================
# PHONE NORMALIZATION TESTS
# =========================================================================


class TestPhoneNormalization:
    """Test phone normalization."""

    def test_strips_formatting(self):
        """Removes all non-digit characters."""
        assert CSVImporter.normalize_phone("(713) 555-1234") == "7135551234"

    def test_strips_dots(self):
        """Removes dots."""
        assert CSVImporter.normalize_phone("713.555.1234") == "7135551234"

    def test_keeps_country_code(self):
        """Preserves country code digits."""
        assert CSVImporter.normalize_phone("+1 713 555 1234") == "17135551234"

    def test_empty_string(self):
        """Empty input returns empty."""
        assert CSVImporter.normalize_phone("") == ""
