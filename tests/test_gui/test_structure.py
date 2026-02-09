"""Test GUI code structure without running tkinter.

Tests that can run in CI without a display.
"""

import ast
import sys
from pathlib import Path


def test_gui_app_structure():
    """Test that app.py has required methods and structure."""
    app_path = Path("src/gui/app.py")
    assert app_path.exists(), "app.py should exist"

    with open(app_path) as f:
        tree = ast.parse(f.read())

    # Find IronLungApp class
    app_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "IronLungApp":
            app_class = node
            break

    assert app_class is not None, "IronLungApp class should exist"

    # Check for required methods
    method_names = {n.name for n in app_class.body if isinstance(n, ast.FunctionDef)}
    required_methods = {
        "__init__",
        "run",
        "_create_window",
        "_create_tabs",
        "_create_status_bar",
        "_bind_shortcuts",
        "close",
        "_on_tab_changed",
        "_update_status_bar",
    }

    for method in required_methods:
        assert method in method_names, f"IronLungApp should have {method} method"


def test_import_tab_structure():
    """Test that import_tab.py has required methods and UI elements."""
    tab_path = Path("src/gui/tabs/import_tab.py")
    assert tab_path.exists(), "import_tab.py should exist"

    with open(tab_path) as f:
        tree = ast.parse(f.read())

    # Find ImportTab class
    tab_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ImportTab":
            tab_class = node
            break

    assert tab_class is not None, "ImportTab class should exist"

    # Check for required methods
    method_names = {n.name for n in tab_class.body if isinstance(n, ast.FunctionDef)}
    required_methods = {
        "__init__",
        "refresh",
        "on_activate",
        "select_file",
        "preview_import",
        "execute_import",
        "_create_ui",
    }

    for method in required_methods:
        assert method in method_names, f"ImportTab should have {method} method"


def test_pipeline_tab_structure():
    """Test that pipeline.py has required methods and UI elements."""
    tab_path = Path("src/gui/tabs/pipeline.py")
    assert tab_path.exists(), "pipeline.py should exist"

    with open(tab_path) as f:
        tree = ast.parse(f.read())

    # Find PipelineTab class
    tab_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PipelineTab":
            tab_class = node
            break

    assert tab_class is not None, "PipelineTab class should exist"

    # Check for required methods
    method_names = {n.name for n in tab_class.body if isinstance(n, ast.FunctionDef)}
    required_methods = {
        "__init__",
        "refresh",
        "on_activate",
        "apply_filters",
        "export_view",
        "bulk_move",
        "bulk_park",
        "_create_ui",
    }

    for method in required_methods:
        assert method in method_names, f"PipelineTab should have {method} method"


def test_theme_structure():
    """Test that theme.py has required functions."""
    theme_path = Path("src/gui/theme.py")
    assert theme_path.exists(), "theme.py should exist"

    with open(theme_path) as f:
        tree = ast.parse(f.read())

    # Check for required functions
    function_names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    required_functions = {"apply_theme", "configure_styles"}

    for func in required_functions:
        assert func in function_names, f"theme.py should have {func} function"

    # Check for COLORS and FONTS dictionaries
    var_names = {
        n.targets[0].id
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }

    assert "COLORS" in var_names, "theme.py should have COLORS dictionary"
    assert "FONTS" in var_names, "theme.py should have FONTS dictionary"


if __name__ == "__main__":
    test_gui_app_structure()
    print("✓ app.py structure is correct")

    test_import_tab_structure()
    print("✓ import_tab.py structure is correct")

    test_pipeline_tab_structure()
    print("✓ pipeline.py structure is correct")

    test_theme_structure()
    print("✓ theme.py structure is correct")

    print("\nAll GUI structure tests passed!")
