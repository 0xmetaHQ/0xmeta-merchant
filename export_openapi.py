"""
Export OpenAPI schema from FastAPI app to JSON file.

Usage:
    uv run export_openapi.py
    uv run export_openapi.py --output openapi.yaml
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def export_openapi(app_import: str, output_file: str = "openapi.json"):
    """
    Export OpenAPI schema from a FastAPI app.
    
    Args:
        app_import: Import path to the FastAPI app (e.g., "main:app")
        output_file: Output file path (supports .json or .yaml)
    """
    # Split the import string
    try:
        module_path, app_name = app_import.split(":")
    except ValueError:
        print(f"Error: Invalid app import string '{app_import}'")
        print("Expected format: 'module.path:app_variable'")
        print("Example: 'main:app' or 'app.main:application'")
        sys.exit(1)
    
    # Import the FastAPI app
    try:
        # Add current directory to path
        sys.path.insert(0, str(Path.cwd()))
        
        # Import the module
        module = __import__(module_path, fromlist=[app_name])
        app = getattr(module, app_name)
    except ImportError as e:
        print(f"Error: Could not import module '{module_path}'")
        print(f"Details: {e}")
        sys.exit(1)
    except AttributeError:
        print(f"Error: Could not find '{app_name}' in module '{module_path}'")
        sys.exit(1)
    
    # Generate OpenAPI schema
    try:
        openapi_schema = app.openapi()
    except Exception as e:
        print(f"Error generating OpenAPI schema: {e}")
        sys.exit(1)
    
    # Write to file
    output_path = Path(output_file)
    
    try:
        if output_path.suffix == ".yaml" or output_path.suffix == ".yml":
            with open(output_path, "w") as f:
                yaml.dump(openapi_schema, f, sort_keys=False, default_flow_style=False)
            print(f"✅ OpenAPI schema exported to {output_file} (YAML)")
        else:
            with open(output_path, "w") as f:
                json.dump(openapi_schema, f, indent=2)
            print(f"✅ OpenAPI schema exported to {output_file} (JSON)")
    except Exception as e:
        print(f"Error writing file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Export OpenAPI schema from FastAPI app"
    )
    parser.add_argument(
        "app",
        nargs="?",
        default="main:app",
        help="App import string (default: main:app)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="openapi.json",
        help="Output file path (default: openapi.json)",
    )
    
    args = parser.parse_args()
    export_openapi(args.app, args.output)


if __name__ == "__main__":
    main()