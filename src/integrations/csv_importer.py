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

import csv
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
        path = Path(path)
        if not path.exists():
            raise ImportError_(f"File not found: {path}")

        suffix = path.suffix.lower()

        if suffix in (".xlsx", ".xls"):
            headers, all_rows = self._parse_xlsx(path)
            encoding = "xlsx"
        elif suffix == ".csv":
            headers, all_rows, encoding = self._parse_csv(path)
        else:
            raise ImportError_(f"Unsupported file type: {suffix}")

        if not headers:
            raise ImportError_("File contains no headers")

        if not all_rows:
            return ParseResult(
                headers=headers,
                sample_rows=[],
                total_rows=0,
                detected_preset=self.detect_preset(headers),
                encoding=encoding,
            )

        sample = all_rows[:5]
        detected = self.detect_preset(headers)

        return ParseResult(
            headers=headers,
            sample_rows=sample,
            total_rows=len(all_rows),
            detected_preset=detected,
            encoding=encoding,
        )

    def detect_preset(self, headers: list[str]) -> Optional[str]:
        """Detect known format from headers.

        Args:
            headers: Column headers

        Returns:
            Preset name ("phoneburner", "aapl") or None
        """
        headers_lower = [h.lower().strip() for h in headers]

        for preset_name, field_map in PRESETS.items():
            matched = 0
            total = len(field_map)
            for _field, column_names in field_map.items():
                for col_name in column_names:
                    if col_name.lower() in headers_lower:
                        matched += 1
                        break
            # If more than half the fields match, it's this preset
            if matched >= total * 0.6:
                return preset_name

        return None

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
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix in (".xlsx", ".xls"):
            headers, all_rows = self._parse_xlsx(path)
        else:
            headers, all_rows, _ = self._parse_csv(path)

        # If preset specified and no mapping, build mapping from preset
        if preset and preset in PRESETS and not mapping:
            mapping = {}
            preset_map = PRESETS[preset]
            headers_lower = {h.lower().strip(): h for h in headers}
            for field, column_names in preset_map.items():
                for col_name in column_names:
                    if col_name.lower() in headers_lower:
                        mapping[field] = headers_lower[col_name.lower()]
                        break

        # Build header index
        header_idx = {h: i for i, h in enumerate(headers)}

        records: list[ImportRecord] = []
        for row in all_rows:
            # Skip rows where all cells are empty or just whitespace
            if all(not (cell and cell.strip()) for cell in row):
                continue

            record = ImportRecord()

            for field, col_name in mapping.items():
                if col_name not in header_idx:
                    continue
                idx = header_idx[col_name]
                if idx >= len(row):
                    continue
                value = (row[idx] or "").strip()
                if not value:
                    continue

                if field == "first_name":
                    # Check if this is a full name field (AAPL preset)
                    if preset == "aapl" and col_name in ("Contact Name",):
                        first, last = self.split_full_name(value)
                        record.first_name = first
                        record.last_name = last
                    else:
                        record.first_name = value
                elif field == "last_name":
                    record.last_name = value
                elif field == "email":
                    record.email = self.normalize_email(value)
                elif field == "phone":
                    record.phone = self.normalize_phone(value)
                elif field == "company_name":
                    record.company_name = value
                elif field == "title":
                    record.title = value
                elif field == "state":
                    record.state = value.upper().strip()[:2]
                elif field == "source":
                    record.source = value
                elif field == "notes":
                    record.notes = value

            # Only include if we have at least a name
            if record.first_name or record.last_name:
                records.append(record)

        return records

    # Delimiters the sniffer is allowed to detect; anything else
    # (e.g. ``@`` from email addresses) is treated as a mis-detection.
    _VALID_DELIMITERS = {",", "\t", ";", "|"}

    def _parse_csv(self, path: Path) -> tuple[list[str], list[list[str]], str]:
        """Parse CSV file, trying multiple encodings.

        Returns:
            Tuple of (headers, all_rows, encoding)
        """
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    # Sniff dialect
                    sample = f.read(8192)
                    f.seek(0)

                    try:
                        dialect = csv.Sniffer().sniff(sample)
                        if dialect.delimiter in self._VALID_DELIMITERS:
                            reader = csv.reader(f, dialect)
                        else:
                            reader = csv.reader(f)
                    except csv.Error:
                        # Sniffer can fail on small/simple files.
                        # Default csv.reader uses comma delimiter,
                        # which handles the majority of imports.
                        reader = csv.reader(f)
                    rows = list(reader)

                    if not rows:
                        return [], [], encoding

                    headers = [str(h).strip() for h in rows[0]]
                    data_rows = []
                    for row in rows[1:]:
                        data_rows.append([str(cell).strip() if cell else "" for cell in row])

                    return headers, data_rows, encoding

            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise ImportError_(f"Cannot parse CSV: {e}") from e

        raise ImportError_(f"Cannot read file with any supported encoding: {path}")

    def _parse_xlsx(self, path: Path) -> tuple[list[str], list[list[str]]]:
        """Parse XLSX file.

        Returns:
            Tuple of (headers, all_rows)
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError_(
                "openpyxl is required for XLSX files. Install with: pip install openpyxl"
            )

        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            ws = wb.active

            rows_iter = ws.iter_rows(values_only=True)

            # First row is headers
            header_row = next(rows_iter, None)
            if header_row is None:
                wb.close()
                return [], []

            headers = [str(cell).strip() if cell else "" for cell in header_row]

            data_rows = []
            for row in rows_iter:
                data_rows.append([str(cell).strip() if cell is not None else "" for cell in row])

            wb.close()
            return headers, data_rows

        except Exception as e:
            raise ImportError_(f"Cannot parse XLSX: {e}") from e

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
