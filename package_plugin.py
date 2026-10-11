#!/usr/bin/env python3
"""
GeoSpatial Tools — Plugin Packaging Script.

Creates a clean, installable zip package (geospatial_tools.zip) suitable for
QGIS's 'Install from ZIP' feature on both Windows and macOS/Linux.
Excludes bytecode, cache folders, and operating system junk files.
"""

import os
import zipfile

def package_plugin():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(repo_root, "geospatial_tools")
    output_zip = os.path.join(repo_root, "geospatial_tools.zip")

    if not os.path.isdir(source_dir):
        print(f"Error: Could not find plugin directory at {source_dir}")
        return False

    # Remove existing zip if present
    if os.path.exists(output_zip):
        os.remove(output_zip)

    ignored_extensions = {".pyc", ".pyo", ".pyd"}
    ignored_names = {"__pycache__", ".DS_Store", "Thumbs.db"}

    file_count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignored_names]

            for file in files:
                if file in ignored_names:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in ignored_extensions:
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, repo_root)
                # Ensure ZIP internal paths use forward slashes (standard across OS)
                arc_name = rel_path.replace(os.sep, "/")
                zf.write(abs_path, arc_name)
                file_count += 1

    size_kb = os.path.getsize(output_zip) / 1024.0
    print(f"Successfully created: {output_zip}")
    print(f"Total files included: {file_count} ({size_kb:.1f} KB)")
    print("\nTo install in QGIS (Windows / macOS / Linux):")
    print("1. Open QGIS.")
    print("2. Menu: Plugins -> Manage and Install Plugins...")
    print("3. Click 'Install from ZIP'.")
    print(f"4. Select '{output_zip}'.")
    print("5. Click 'Install Plugin'.")
    return True

if __name__ == "__main__":
    package_plugin()
