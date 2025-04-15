from typing import List, Dict, Any, Optional
import csv
import random
import re
import subprocess
import json
import os
import shutil
from pathlib import Path
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QSize, Qt
import sys
import glob

# Default settings
DEFAULT_TAG_CATEGORIES = {
    'artist': False,
    'copyright': False,
    'character': False,
    'species': False,
    'general': True
}

class TagFetcher:
    """Class to handle tag fetching from e621 and danbooru"""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.e621_artists = []
        self.danbooru_artists = []
        self.load_artists()
        
        # Default to system Python
        self.external_python = "python3" if not sys.platform.startswith('win') else "python"
        
        # Platform-specific settings
        if sys.platform.startswith('win'):
            # Windows paths
            self.python_lib_path = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "krita" / "pykrita" / "ai_diffusion" / "venv"
        else:
            # Linux paths
            self.python_lib_path = Path.home() / ".local" / "share" / "krita" / "pykrita" / "ai_diffusion" / "venv"
        
        # Path to helper script using Path for cross-platform compatibility
        self.helper_script = Path(__file__).parent / "fetch_helper.py"
        
    def load_artists(self):
        """Load artist lists from CSV files"""
        self.e621_artists = []
        self.danbooru_artists = []

        try:
            # Load e621 artists
            e621_file = Path(__file__).parent / "e621_artist_webui.csv"
            if e621_file.exists():
                with open(e621_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.e621_artists.extend([row['trigger'] for row in reader])
                print(f"Loaded {len(self.e621_artists)} e621 artists")

            # Load danbooru artists
            danbooru_file = Path(__file__).parent / "danbooru_artist_webui.csv"
            if danbooru_file.exists():
                with open(danbooru_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.danbooru_artists.extend([row['trigger'] for row in reader])
                print(f"Loaded {len(self.danbooru_artists)} Danbooru artists")

        except Exception as e:
            print(f"Error loading artists: {e}")
    
    def get_random_artist(self, source="e621"):
        """Get a random artist from specified source"""
        artists = self.e621_artists if source == "e621" else self.danbooru_artists
        if not artists:
            print(f"No artists loaded from {source}")
            return None
            
        return random.choice(artists)

    def set_python_path(self, python_path):
        """Set the path to the external Python interpreter"""
        self.external_python = python_path
    
    def _format_tag(self, tag: str, category: str) -> str:
        """Format a tag based on its category and content."""
        tag = tag.strip()
        
        if category == 'artist':
            if tag.startswith('artist:'):
                tag = tag[7:]
            tag = f"artist:{tag}"
        
        if '(' in tag or ')' in tag:
            tag = tag.replace('(', '\\(').replace(')', '\\)')
            
        return tag

    def _process_tag_list(self, tag_list, category: str, unwanted_tags: list) -> list[str]:
        """Process a list of tags and format them appropriately."""
        tags = []
        for tag in tag_list:
            if tag and tag not in unwanted_tags:
                formatted_tag = self._format_tag(tag, category)
                tags.append(formatted_tag)
        return tags

    def _get_linux_python_path(self):
        """Find the best Python executable to use on Linux"""
        # First try the venv Python if it exists
        venv_python = self.python_lib_path / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        
        # Then try system Python 3
        python3_path = shutil.which("python3")
        if python3_path:
            return python3_path
            
        # Fallback to whatever Python is in PATH
        python_path = shutil.which("python")
        if python_path:
            return python_path
            
        return None

    def fetch_tags_via_external_script(self, site="e621", solo_required=False, unwanted_tags=None):
        """
        Use a platform-appropriate method to call the fetch_helper.py script with a clean environment
        """
        if unwanted_tags is None:
            unwanted_tags = []
        
        if not self.helper_script.exists():
            print(f"Helper script not found at {self.helper_script}")
            return None
        
        try:
            is_windows = sys.platform.startswith('win')
            
            if is_windows:
                # Windows: Create and use batch file approach
                batch_file = Path(__file__).parent / "run_fetch.bat"
                if not batch_file.exists():
                    with open(batch_file, 'w') as f:
                        f.write('@echo off\n')
                        f.write('setlocal EnableDelayedExpansion\n\n')
                        
                        f.write('REM Clear PYTHONPATH to avoid conflicts\n')
                        f.write('SET "PYTHONPATH="\n\n')
                        
                        f.write('REM Try to find Python in common locations\n')
                        f.write('SET "PYTHON_EXE="\n\n')
                        
                        # Check LocalAppData first with explicit existence check
                        f.write('REM Check Python in LocalAppData\n')
                        f.write('SET "PY_LOC=%LOCALAPPDATA%\\Programs\\Python\\Python313\\python.exe"\n')
                        f.write('IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%LOCALAPPDATA%\\Programs\\Python\\Python312\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%LOCALAPPDATA%\\Programs\\Python\\Python310\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%LOCALAPPDATA%\\Programs\\Python\\Python39\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        # Program Files
                        f.write('REM Check Program Files locations\n')
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%PROGRAMFILES%\\Python\\Python313\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%PROGRAMFILES%\\Python\\Python312\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%PROGRAMFILES(X86)%\\Python\\Python313\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=%PROGRAMFILES(X86)%\\Python\\Python312\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        # Direct paths
                        f.write('REM Check direct Python paths\n')
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=C:\\Python313\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    SET "PY_LOC=C:\\Python312\\python.exe"\n')
                        f.write('    IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        # Fallback to PATH with verification
                        f.write('REM Fallback to PATH\n')
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    FOR %%I IN (python.exe) DO SET "PY_LOC=%%~$PATH:I"\n')
                        f.write('    IF NOT "!PY_LOC!"=="" IF EXIST "!PY_LOC!" SET "PYTHON_EXE=!PY_LOC!"\n')
                        f.write(')\n\n')
                        
                        f.write('REM Check if Python was found\n')
                        f.write('IF NOT DEFINED PYTHON_EXE (\n')
                        f.write('    ECHO ERROR: Python not found. Please install Python 3.9+ >&2\n')
                        f.write('    EXIT /B 1\n')
                        f.write(')\n\n')
                        
                        f.write('REM Double-check Python exists\n')
                        f.write('IF NOT EXIST "!PYTHON_EXE!" (\n')
                        f.write('    ECHO ERROR: Python executable not found at !PYTHON_EXE! >&2\n')
                        f.write('    EXIT /B 1\n')
                        f.write(')\n\n')
                        
                        f.write('REM Run the helper script\n')
                        f.write('REM ECHO Using Python: !PYTHON_EXE!\n')
                        f.write('"!PYTHON_EXE!" "%~dp0fetch_helper.py" %*\n')
                        f.write('EXIT /B %ERRORLEVEL%\n')
                
                # Build command with parameters for Windows
                cmd = [
                    str(batch_file),
                    site,
                    "true" if solo_required else "false",
                    ",".join(unwanted_tags)
                ]
            else:
                # Linux/macOS: Use direct Python execution
                python_path = self._get_linux_python_path()
                if not python_path:
                    print("Python executable not found. Please install Python 3.")
                    return None
                    
                cmd = [
                    python_path,
                    str(self.helper_script),
                    site,
                    "true" if solo_required else "false",
                    ",".join(unwanted_tags)
                ]
            
            # Create clean environment
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)  # Remove PYTHONPATH to avoid conflicts
            
            # On Linux, ensure we have the venv's site-packages in PATH if using venv Python
            if not is_windows and python_path.startswith(str(self.python_lib_path)):
                site_packages = str(self.python_lib_path / "lib" / "python*/site-packages")
                site_packages_paths = glob.glob(site_packages)
                if site_packages_paths:
                    env['PYTHONPATH'] = os.pathsep.join(site_packages_paths)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env
            )
            
            if result.returncode != 0:
                print(f"Error in external script: Command {cmd} returned {result.returncode}")
                print(f"stderr: {result.stderr}")
                return None
                
            try:
                output = json.loads(result.stdout.strip())
                if "error" in output:
                    print(f"Error from helper script: {output['error']}")
                    return None
                    
                if "tags" not in output:
                    print("No tags in helper script response")
                    return None
                    
                tag_categories = DEFAULT_TAG_CATEGORIES
                if self.settings and hasattr(self.settings, 'tag_categories'):
                    if self.settings.tag_categories:
                        tag_categories = self.settings.tag_categories
                
                tags_output = []
                for category, enabled in tag_categories.items():
                    if not enabled:
                        continue
                        
                    if site == "danbooru" and category == 'species':
                        continue
                        
                    category_tags = output["tags"].get(category, [])
                    formatted_tags = self._process_tag_list(category_tags, category, unwanted_tags)
                    tags_output.extend(formatted_tags)
                    
                if not tags_output:
                    print("No valid tags found after filtering")
                    return None
                    
                return tags_output
                
            except json.JSONDecodeError:
                print(f"Failed to parse JSON from helper script")
                print(f"Raw output: {result.stdout}")
                return None
                
        except subprocess.CalledProcessError as e:
            print(f"Error in external script: {e}")
            print(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Failed to run external script: {e}")
            return None

    def get_random_tags(self, site="e621"):
        """Get random tags from specified site"""
        try:
            require_solo = False
            if self.settings and hasattr(self.settings, 'require_solo'):
                require_solo = self.settings.require_solo
                
            unwanted_tags = []
            if self.settings and hasattr(self.settings, 'unwanted_tags'):
                if self.settings.unwanted_tags:
                    unwanted_tags = self.settings.unwanted_tags
            
            return self.fetch_tags_via_external_script(
                site=site,
                solo_required=require_solo,
                unwanted_tags=unwanted_tags
            )
                    
        except Exception as e:
            print(f"Error in get_random_tags: {e}")
            return None


def download_site_icons():
    """Download site icons if they don't exist locally"""
    import urllib.request
    
    icons_dir = Path(__file__).parent / "resources"
    icons_dir.mkdir(exist_ok=True)
    
    icons = {
        'e621': {
            'url': 'https://e621.net/packs/static/main-logo-2653c015c5870ec4ff08.svg',
            'file': 'e621-icon.svg'
        },
        'danbooru': {
            'url': 'https://danbooru.donmai.us/favicon.svg',
            'file': 'danbooru-icon.svg'
        }
    }
    
    for site, info in icons.items():
        icon_path = icons_dir / info['file']
        if not icon_path.exists():
            try:
                with urllib.request.urlopen(info['url']) as response:
                    content = response.read().decode('utf-8')
                    with open(icon_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Downloaded {site} icon")
            except Exception as e:
                print(f"Error downloading {site} icon: {e}")

def create_site_icon(site_name: str) -> QIcon:
    """Create a QIcon from site SVG"""
    icon_path = Path(__file__).parent / "resources" / f"{site_name}-icon.svg"
    
    if not icon_path.exists():
        download_site_icons()
    
    if not icon_path.exists():
        return QIcon()
        
    icon = QIcon()
    renderer = QSvgRenderer(str(icon_path))
    
    for size in [16, 24, 32, 48]:
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
        
    return icon