"""Tests for CSV/XLSX importer."""

import pytest
from pathlib import Path
from src.integrations.csv_importer import CSVImporter, ParseResult


class TestCSVImporter:
    """Test CSVImporter class."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_parse_csv_file(self, tmp_path: Path):
        """Can parse CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("first_name,last_name,email\nJohn,Doe,john@test.com\n")
        
        importer = CSVImporter()
        result = importer.parse_file(str(csv_file), {})
        assert len(result.records) == 1
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_detect_preset(self, tmp_path: Path):
        """Detects known file format preset."""
        pass


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
        # Basic normalization doesn't validate - just normalizes
        assert CSVImporter.normalize_email("not-an-email") == "not-an-email"
        assert CSVImporter.normalize_email("") == ""
