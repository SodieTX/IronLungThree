"""Integration test for GUI components without requiring display.

This test validates the logic and structure without actually running tkinter.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))


def test_gui_app_initialization():
    """Test that IronLungApp can be initialized with mock tkinter."""
    # Mock tkinter before import
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.filedialog'] = MagicMock()
    sys.modules['tkinter.messagebox'] = MagicMock()
    
    from src.gui.app import IronLungApp
    from src.db.database import Database
    
    # Create mock database
    mock_db = MagicMock(spec=Database)
    mock_db.get_prospects.return_value = []
    
    # Initialize app (should not fail)
    app = IronLungApp(mock_db)
    
    assert app.db is mock_db
    assert app.root is None
    assert app._notebook is None
    
    print("✓ IronLungApp initializes correctly")


def test_import_tab_initialization():
    """Test that ImportTab can be initialized."""
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.filedialog'] = MagicMock()
    sys.modules['tkinter.messagebox'] = MagicMock()
    
    from src.gui.tabs.import_tab import ImportTab
    
    mock_parent = MagicMock()
    mock_db = MagicMock()
    
    tab = ImportTab(mock_parent, mock_db)
    
    assert tab.db is mock_db
    assert tab._selected_file is None
    
    print("✓ ImportTab initializes correctly")


def test_pipeline_tab_initialization():
    """Test that PipelineTab can be initialized."""
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.filedialog'] = MagicMock()
    sys.modules['tkinter.messagebox'] = MagicMock()
    
    from src.gui.tabs.pipeline import PipelineTab
    
    # Mock a frame
    mock_frame = MagicMock()
    mock_frame.winfo_children.return_value = []
    
    mock_parent = MagicMock()
    mock_db = MagicMock()
    
    tab = PipelineTab(mock_parent, mock_db)
    tab.frame = mock_frame  # Set frame to enable _create_ui
    
    assert tab.db is mock_db
    # Tree should be created during initialization now
    assert hasattr(tab, '_tree')
    
    print("✓ PipelineTab initializes correctly")


def test_csv_importer_integration():
    """Test CSV importer can be imported and has expected interface."""
    from src.integrations.csv_importer import CSVImporter, ParseResult
    
    importer = CSVImporter()
    
    # Check methods exist
    assert hasattr(importer, 'parse_file')
    assert hasattr(importer, 'detect_preset')
    assert hasattr(importer, 'apply_mapping')
    
    print("✓ CSVImporter integration is correct")


def test_intake_funnel_integration():
    """Test intake funnel can be imported and has expected interface."""
    from src.db.intake import IntakeFunnel
    
    mock_db = MagicMock()
    funnel = IntakeFunnel(mock_db)
    
    # Check methods exist
    assert hasattr(funnel, 'analyze')
    assert hasattr(funnel, 'commit')
    
    print("✓ IntakeFunnel integration is correct")


def test_database_methods_exist():
    """Test that Database has required methods for GUI."""
    from src.db.database import Database
    
    # Check methods exist (don't need to call them)
    assert hasattr(Database, 'get_prospects')
    assert hasattr(Database, 'get_prospect')
    assert hasattr(Database, 'get_company')
    assert hasattr(Database, 'bulk_update_population')
    assert hasattr(Database, 'bulk_park')
    assert hasattr(Database, 'get_activities')
    
    print("✓ Database has all required methods")


def test_models_enums_exist():
    """Test that required enums exist."""
    from src.db.models import Population, ActivityType
    
    # Check Population enum values
    assert hasattr(Population, 'BROKEN')
    assert hasattr(Population, 'UNENGAGED')
    assert hasattr(Population, 'ENGAGED')
    assert hasattr(Population, 'PARKED')
    assert hasattr(Population, 'DEAD_DNC')
    assert hasattr(Population, 'LOST')
    assert hasattr(Population, 'PARTNERSHIP')
    assert hasattr(Population, 'CLOSED_WON')
    
    # Check ActivityType has IMPORT
    assert hasattr(ActivityType, 'IMPORT')
    
    print("✓ All required model enums exist")


if __name__ == "__main__":
    # Run tests
    test_gui_app_initialization()
    test_import_tab_initialization()
    test_pipeline_tab_initialization()
    test_csv_importer_integration()
    test_intake_funnel_integration()
    test_database_methods_exist()
    test_models_enums_exist()
    
    print("\n✅ All integration tests passed!")
