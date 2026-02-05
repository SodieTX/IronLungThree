"""CSV and XLSX file importer with column mapping.

Provides:
    - CSV and XLSX parsing
    - Preset detection (PhoneBurner, AAPL)
    - Column mapping UI support
    - Data normalization

Usage:
    from src.integrations.csv_importer import CSVImporter
    
    importer = CSVImporter()
    result = importer.parse_file(Path("contacts.csv"))
    records = importer.apply_mapping(path, mapping)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.core.exceptions import ImportError_
from src.core.logging import get_logger
from src.db.intake import ImportRecord

logger = get_logger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a CSV/XLSX file.
    
    Attributes:
        headers: Column headers
        sample_rows: First 5 rows of data
        total_rows: Total data rows
        detected_preset: Auto-detected preset (if any)
        encoding: File encoding used
    """
    headers: list[str]
    sample_rows: list[list[str]]
    total_rows: int
    detected_preset: Optional[str] = None
    encoding: str = "utf-8"


# Preset column mappings
PRESETS = {
    "phoneburner": {
        "first_name": ["First Name", "FirstName", "first_name"],
        "last_name": ["Last Name", "LastName", "last_name"],
        "email": ["Email", "Email Address", "email"],
        "phone": ["Phone", "Phone Number", "phone"],
        "company_name": ["Company", "Company Name", "company"],
        "title": ["Title", "Job Title", "title"],
        "state": ["State", "state"],
    },
    "aapl": {
        "first_name": ["Contact Name"],  # Will need splitting
        "email": ["Email Address", "Email"],
        "phone": ["Phone Number", "Phone"],
        "company_name": ["Organization", "Company"],
        "state": ["State"],
    },
}


class CSVImporter:
    """CSV and XLSX file importer.
    
    Handles:
        - Multiple encodings (UTF-8, Latin-1, CP1252)
        - Excel files (requires openpyxl)
        - Preset detection
        - Data normalization
    """
    
    def parse_file(self, path: Path) -> ParseResult:
        """Parse CSV or XLSX file.
        
        Args:
            path: Path to file
            
        Returns:
            ParseResult with headers and sample data
            
        Raises:
            ImportError_: If file cannot be parsed
        """
        raise NotImplementedError("Phase 1, Step 1.12")
        
    def detect_preset(self, headers: list[str]) -> Optional[str]:
        """Detect known format from headers.
        
        Args:
            headers: Column headers
            
        Returns:
            Preset name ("phoneburner", "aapl") or None
        """
        raise NotImplementedError("Phase 1, Step 1.12")
        
    def apply_mapping(
        self,
        path: Path,
        mapping: dict[str, str],
        preset: Optional[str] = None,
    ) -> list[ImportRecord]:
        """Apply column mapping and return normalized records.
        
        Args:
            path: Path to file
            mapping: Dict of field_name -> column_name
            preset: Optional preset to use
            
        Returns:
            List of ImportRecord objects
        """
        raise NotImplementedError("Phase 1, Step 1.12")
        
    def _parse_csv(self, path: Path) -> tuple[list[str], list[list[str]], str]:
        """Parse CSV file, trying multiple encodings.
        
        Returns:
            Tuple of (headers, all_rows, encoding)
        """
        raise NotImplementedError("Phase 1, Step 1.12")
        
    def _parse_xlsx(self, path: Path) -> tuple[list[str], list[list[str]]]:
        """Parse XLSX file.
        
        Returns:
            Tuple of (headers, all_rows)
        """
        raise NotImplementedError("Phase 1, Step 1.12")
        
    @staticmethod
    def split_full_name(full_name: str) -> tuple[str, str]:
        """Split full name into first and last.
        
        "John Smith" -> ("John", "Smith")
        "Mary Jane Watson" -> ("Mary", "Jane Watson")
        
        Args:
            full_name: Full name string
            
        Returns:
            Tuple of (first_name, last_name)
        """
        parts = full_name.strip().split(None, 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return parts[0], ""
        return "", ""
        
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone to digits only.
        
        "(713) 555-1234" -> "7135551234"
        """
        return "".join(c for c in phone if c.isdigit())
        
    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize email to lowercase.
        
        "JOHN@ABC.COM" -> "john@abc.com"
        """
        return email.lower().strip()
