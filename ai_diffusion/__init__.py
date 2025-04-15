"""Generative AI plugin for Krita"""

__version__ = "1.33.0"

import importlib.util
import sys
import os
import glob
from pathlib import Path

# Detect operating system
is_windows = os.name == 'nt'

# Set up virtual environment paths based on OS
if is_windows:
    # Windows paths
    venv_path = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "krita" / "pykrita" / "ai_diffusion" / "venv"
    site_packages_paths = [venv_path / "Lib" / "site-packages"]
else:
    # Linux/macOS paths
    venv_path = Path.home() / ".local" / "share" / "krita" / "pykrita" / "ai_diffusion" / "venv"
    # Find all possible python version site-packages directories
    site_packages_paths = glob.glob(str(venv_path / "lib" / "python*" / "site-packages"))

# Add valid site-packages paths to sys.path
for path in site_packages_paths:
    path_str = str(path) if isinstance(path, Path) else path
    if os.path.exists(path_str) and path_str not in sys.path:
        sys.path.insert(0, path_str)

# Verify websockets module is available
if not importlib.util.find_spec(".websockets.src", "ai_diffusion"):
    raise ImportError(
        "Could not find websockets module. This indicates that it was not installed with the"
        " plugin. Please make sure to download a plugin release package (NOT just the source!). You"
        " can find the latest release package here:"
        " https://github.com/Acly/krita-ai-diffusion/releases"
    )

# Check for other required modules
REQUIRED_MODULES = ["beautifulsoup4", "requests", "curl_cffi", "PyQt5"]
INSTALL_MODULES = ["beautifulsoup4", "requests", "curl-cffi", "PyQt5"]  # Package names for pip install
missing_modules = []

for i, module in enumerate(REQUIRED_MODULES):
    module_name = module.split("[")[0]  # Handle module[extra] syntax
    if not importlib.util.find_spec(module_name):
        missing_modules.append(INSTALL_MODULES[i])

# If dependencies are missing, install them automatically
if missing_modules:
    print(f"Installing missing dependencies: {', '.join(missing_modules)}")
    # Import the dependency installer and run it
    from .dependency_installer import install_dependencies_sync
    try:
        install_dependencies_sync()
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        # We'll continue loading the plugin, but features requiring these dependencies won't work

# The following imports depend on the code running inside Krita, so they cannot be imported in tests.
if importlib.util.find_spec("krita"):
    from .extension import AIToolsExtension as AIToolsExtension