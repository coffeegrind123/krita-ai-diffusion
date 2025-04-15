"""Package dependency installer for AI Tools plugin."""
from __future__ import annotations
import asyncio
import shutil
import re
import os
import zipfile
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Callable, NamedTuple, Optional, Union
import sys
import subprocess

# Determine if running on Windows
is_windows = sys.platform.startswith('win')
_exe = ".exe" if is_windows else ""


class InstallState(Enum):
    not_installed = 0
    installing = 1
    installed = 2
    error = 3


class InstallationProgress(NamedTuple):
    stage: str
    progress: Optional[object] = None
    message: str = ""


Callback = Callable[[InstallationProgress], None]
InternalCB = Callable[[str, Union[str, object]], None]


# Simple logger implementation
class Logger:
    @staticmethod
    def info(message):
        print(f"INFO: {message}")

    @staticmethod
    def error(message):
        print(f"ERROR: {message}")

    @staticmethod
    def warning(message):
        print(f"WARNING: {message}")

    @staticmethod
    def exception(message):
        print(f"EXCEPTION: {message}")


log = Logger()


class DependencyInstaller:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or Path(__file__).parent / "venv")
        self.state = InstallState.not_installed
        self._python_cmd = None
        self._cache_dir = self.path.parent / ".cache"
        self._version_file = self.path.parent / ".deps_version"
        self.check_install()

    def check_install(self):
        """Check if dependencies are already installed"""
        if self._version_file.exists():
            with open(self._version_file, 'r') as f:
                self.version = f.read().strip()
            log.info(f"Found dependencies v{self.version}")
            self.state = InstallState.installed
        else:
            self.version = None
            
        # Check for Python
        if is_windows:
            # Try to find Python directly in Windows default locations first
            system_python_paths = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Python'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Python'),
                os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Programs', 'Python')
            ]
            
            # Look for Python in common locations
            for base_path in system_python_paths:
                if os.path.exists(base_path):
                    for py_dir in os.listdir(base_path):
                        if py_dir.startswith('Python'):
                            python_exe = os.path.join(base_path, py_dir, 'python.exe')
                            if os.path.exists(python_exe):
                                self._python_cmd = Path(python_exe)
                                log.info(f"Found system Python at {python_exe}")
                                return
            
            # Look for Python in standard locations
            python_pkg = ["python3.dll", "python.exe"]
            python_search_paths = [self.path.parent / "python", self.path / "Scripts"]
            
            # Also check in Krita's Python location
            krita_python = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "lib", "Python")
            if os.path.exists(krita_python):
                python_search_paths.append(Path(krita_python))
        else:
            # Unix systems
            python_pkg = ["python3", "pip3"]
            python_search_paths = [self.path.parent / "python", self.path / "bin"]
            
        python_path = _find_component(python_pkg, python_search_paths)
        if python_path is None:
            if is_windows:
                # Try direct python executables with .exe extension
                self._python_cmd = _find_program(
                    "python3.13.exe", "python3.12.exe", "python3.11.exe", "python3.10.exe", "python3.exe", "python.exe"
                )
                
                # If still not found, try direct paths with common Python install locations
                if self._python_cmd is None:
                    common_python_paths = [
                        r"C:\Python313\python.exe",
                        r"C:\Python312\python.exe",
                        r"C:\Python311\python.exe",
                        r"C:\Python310\python.exe",
                        r"C:\Python39\python.exe",
                        r"C:\Python38\python.exe",
                        r"C:\Program Files\Python313\python.exe",
                        r"C:\Program Files\Python312\python.exe",
                        r"C:\Program Files\Python311\python.exe",
                        r"C:\Program Files\Python310\python.exe",
                        r"C:\Program Files\Python39\python.exe",
                        r"C:\Program Files\Python38\python.exe",
                        r"C:\Program Files (x86)\Python313\python.exe",
                        r"C:\Program Files (x86)\Python312\python.exe",
                        r"C:\Program Files (x86)\Python311\python.exe",
                        r"C:\Program Files (x86)\Python310\python.exe",
                        r"C:\Program Files (x86)\Python39\python.exe",
                        r"C:\Program Files (x86)\Python38\python.exe"
                    ]
                    
                    for py_path in common_python_paths:
                        if os.path.exists(py_path):
                            self._python_cmd = Path(py_path)
                            log.info(f"Found Python at fixed path: {py_path}")
                            break
            else:
                self._python_cmd = _find_program(
                    "python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"
                )
        else:
            if is_windows:
                self._python_cmd = python_path / f"python{_exe}"
            else:
                self._python_cmd = python_path / f"python3{_exe}"

    async def _install(self, cb: InternalCB):
        """Handle the installation process"""
        self.state = InstallState.installing
        cb("Installing", f"Installation started in {self.path}")

        os.makedirs(self._cache_dir, exist_ok=True)
        with open(self._version_file, 'w') as f:
            f.write("incomplete")

        if is_windows and self._python_cmd is None:
            # On Windows install an embedded version of Python
            python_dir = self.path.parent / "python"
            self._python_cmd = python_dir / f"python{_exe}"
            await install_if_missing(python_dir, self._install_python, cb)
        elif not is_windows and not self.path.exists():
            # On Linux a system Python is required to create a virtual environment
            await install_if_missing(self.path, self._create_venv, cb)
            self._python_cmd = self.path / "bin" / "python3"
        
        if self._python_cmd is None:
            raise Exception("Python executable not found. Please install Python 3.9 or newer.")
            
        await self._log_python_version()

        # Install required packages
        await self._install_required_packages(cb)

        with open(self._version_file, 'w') as f:
            f.write("1.0.0")
            
        self.state = InstallState.installed
        cb("Finished", f"Installation finished in {self.path}")
        self.check_install()

    async def _log_python_version(self):
        """Log Python and pip versions"""
        if self._python_cmd is not None:
            python_ver = await get_python_version_string(self._python_cmd)
            log.info(f"Using Python: {python_ver}, {self._python_cmd}")
            pip_ver = await get_python_version_string(self._python_cmd, "-m", "pip")
            log.info(f"Using pip: {pip_ver}")

    def _pip_install(self, *args):
        """Create pip install command with target directory"""
        site_packages = self.path / "Lib" / "site-packages" if is_windows else self.path / "lib" / "python3.11" / "site-packages"
        os.makedirs(site_packages, exist_ok=True)
        return [str(self._python_cmd), "-m", "pip", "install", "--target", str(site_packages), *args]

    async def _install_python(self, cb: InternalCB):
        """Install Python (Windows)"""
        cb("Installing Python", "Downloading Python 3.11.9")
        url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
        archive_path = self._cache_dir / "python-3.11.9-embed-amd64.zip"
        dir = self.path.parent / "python"
        os.makedirs(dir, exist_ok=True)

        # Download Python if needed
        if not archive_path.exists():
            cb("Installing Python", f"Downloading Python from {url}")
            try:
                urllib.request.urlretrieve(url, archive_path)
            except Exception as e:
                raise Exception(f"Failed to download Python: {e}")

        # Extract Python
        cb("Installing Python", f"Extracting Python to {dir}")
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dir)
        except Exception as e:
            raise Exception(f"Failed to extract Python: {e}")

        # Patch the Python path file to enable pip
        python_pth = dir / "python311._pth"
        cb("Installing Python", f"Patching {python_pth}")
        try:
            with open(python_pth, "a") as file:
                file.write("\nimport site\n")
        except Exception as e:
            raise Exception(f"Failed to patch Python path file: {e}")

        # Download and install pip
        git_pip_url = "https://bootstrap.pypa.io/get-pip.py"
        get_pip_file = dir / "get-pip.py"
        
        cb("Installing Python", f"Downloading pip from {git_pip_url}")
        try:
            urllib.request.urlretrieve(git_pip_url, get_pip_file)
        except Exception as e:
            raise Exception(f"Failed to download pip installer: {e}")
            
        await _execute_process("Python", [str(self._python_cmd), str(get_pip_file)], dir, cb)
        await _execute_process("Python", self._pip_install("wheel", "setuptools"), dir, cb)
        cb("Installing Python", "Finished installing Python")

    async def _create_venv(self, cb: InternalCB):
        """Create a Python virtual environment (non-Windows)"""
        cb("Creating Python virtual environment", f"Creating venv in {self.path}")
        assert self._python_cmd is not None
        python_version, major, minor = await get_python_version(self._python_cmd)
        if major is not None and minor is not None and (major < 3 or minor < 9):
            raise Exception(
                f"Python version 3.9 or higher is required, but found {python_version} at {self._python_cmd}. Please make sure a compatible version of Python is installed."
            )
        venv_cmd = [str(self._python_cmd), "-m", "venv", str(self.path)]
        await _execute_process("Python", venv_cmd, self.path.parent, cb)

    async def _install_required_packages(self, cb: InternalCB):
        """Install the required packages"""
        cb("Installing Required Packages", "Installing beautifulsoup4, requests, curl-cffi, PyQt5")
        packages = ["beautifulsoup4", "requests", "curl-cffi", "PyQt5"]
        await _execute_process("Packages", self._pip_install(*packages), self.path.parent, cb)
        cb("Installing Packages", "Finished installing required packages")

    async def install(self, callback: Callback = None):
        """Main installation method"""
        if callback is None:
            # Use a silent callback by default
            callback = lambda progress: None
            
        if not is_windows and self._python_cmd is None:
            raise Exception(
                "Python not found. Please install python3, python3-venv via your package manager and restart."
            )

        def cb(stage: str, message: str | object):
            out_message = ""
            progress = None
            filters = ["Downloading", "Installing", "Collecting", "Using"]
            if isinstance(message, str):
                log.info(message)
                if any(s in message[:16] for s in filters):
                    out_message = message
            else:
                progress = message
            callback(InstallationProgress(stage, progress, out_message))

        try:
            await self._install(cb)
            return True
        except Exception as e:
            log.exception(str(e))
            log.error("Installation failed")
            self.state = InstallState.error
            self.check_install()
            raise Exception(str(e))


# Helper functions
def _find_component(files: list[str], search_paths: list[Path]):
    """Find a component by checking if all files exist in any of the search paths"""
    for path in search_paths:
        if path.exists() and all(path.joinpath(file).exists() for file in files):
            return path
    return None


def _find_program(*commands: str):
    """Find a program in the system PATH"""
    for command in commands:
        p = shutil.which(command)
        if p is not None:
            return Path(p)
    return None


def _get_clean_env():
    """Get a clean environment without PYTHONPATH to avoid conflicts"""
    env = os.environ.copy()
    # Remove problematic environment variables
    if 'PYTHONPATH' in env:
        del env['PYTHONPATH']
    # Add empty PYTHONPATH to ensure it's not inherited
    env['PYTHONPATH'] = ''
    return env


async def _execute_process(name: str, cmd: list, cwd: Path, cb: InternalCB):
    """Execute a process and log output"""
    cmd = [str(c) for c in cmd]
    cb(f"Installing {name}", f"Executing {' '.join(cmd)}")
    
    # Get clean environment without PYTHONPATH conflicts
    env = _get_clean_env()
    
    # Windows-specific handling for subprocess
    if is_windows:
        # Use asyncio.WindowsProactorEventLoopPolicy for Windows
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            # Not available in all Python versions
            pass
            
        # Create startupinfo to hide console window on Windows
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        # For Windows, use a different approach if needed
        try:
            # Try using a direct subprocess call first, which may be more reliable
            if not asyncio.get_event_loop().is_running():
                try:
                    # Synchronous subprocess call as a fallback
                    result = subprocess.run(
                        cmd,
                        cwd=cwd,
                        env=env,  # Use clean environment
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        startupinfo=startupinfo,
                        check=True
                    )
                    
                    # Process output
                    for line in result.stdout.splitlines():
                        cb(f"Installing {name}", line)
                    
                    return
                except subprocess.CalledProcessError as e:
                    raise Exception(f"Error during installation: {e.stderr}")
            
            # Continue with async if the above didn't work or the loop is running
            process = await asyncio.create_subprocess_exec(
                cmd[0], *cmd[1:], 
                cwd=cwd,
                env=env,  # Use clean environment
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startupinfo
            )
        except Exception as e:
            # Fallback if the above fails
            log.warning(f"Falling back to basic subprocess due to: {e}")
            process = await asyncio.create_subprocess_exec(
                cmd[0], *cmd[1:], 
                cwd=cwd,
                env=env,  # Use clean environment 
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
    else:
        # For non-Windows platforms
        process = await asyncio.create_subprocess_exec(
            cmd[0], *cmd[1:], 
            cwd=cwd,
            env=env,  # Use clean environment
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    
    stdout, stderr = await process.communicate()
    
    if stdout:
        for line in stdout.decode('utf-8', errors='replace').splitlines():
            cb(f"Installing {name}", line)
    
    if process.returncode != 0:
        errlog = stderr.decode('utf-8', errors='replace') if stderr else f"Process exited with code {process.returncode}"
        raise Exception(f"Error during installation: {errlog}")


async def install_if_missing(path: Path, installer, *args):
    """Install a component if it's not already installed"""
    if not path.exists():
        await installer(*args)


async def get_python_version_string(python_cmd: Path, *args: str):
    """Get Python version string"""
    cmd_list = [str(python_cmd)]
    cmd_list.extend(args)
    cmd_list.append("--version")
    
    # Get clean environment
    env = _get_clean_env()
    
    if is_windows:
        # Windows-specific handling
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            pass
        
        # Try a direct subprocess call first
        if not asyncio.get_event_loop().is_running():
            try:
                result = subprocess.run(
                    cmd_list,
                    env=env,  # Use clean environment
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                output = result.stdout.strip()
                if not output and result.stderr:
                    output = result.stderr.strip()
                return output
            except Exception:
                pass  # Fall back to asyncio approach
            
    # Use asyncio approach
    proc = await asyncio.create_subprocess_exec(
        *cmd_list, 
        env=env,  # Use clean environment
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    
    # Python might output version to stderr in some cases
    output = out.decode('utf-8', errors='replace').strip()
    if not output and err:
        output = err.decode('utf-8', errors='replace').strip()
        
    return output


async def get_python_version(python_cmd: Path, *args: str):
    """Get Python version numbers"""
    string = await get_python_version_string(python_cmd, *args)
    matches = re.match(r"Python (\d+)\.(\d+)", string)
    if not matches:
        log.warning(f"Could not determine Python version: {string}")
        return string, None, None
    else:
        return string, int(matches.group(1)), int(matches.group(2))


# Main function that will be called from the plugin
async def install_dependencies(callback: Callback = None):
    """Install the required dependencies"""
    installer = DependencyInstaller()
    return await installer.install(callback)


# Function to be called from __init__.py that doesn't use asyncio
def install_dependencies_sync(callback: Callback = None):
    """Synchronous wrapper around install_dependencies"""
    try:
        # Set the right event loop policy for Windows
        if is_windows:
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except AttributeError:
                pass
                
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the installation
        return loop.run_until_complete(install_dependencies(callback))
    except Exception as e:
        log.error(f"Failed to install dependencies: {e}")
        return False