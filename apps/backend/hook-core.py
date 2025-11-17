"""
PyInstaller hook for core package
Ensures all core submodules are properly collected
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all submodules from core package
hiddenimports = collect_submodules('core')

# Also collect data files if any
datas, binaries, hiddenimports_extra = collect_all('core')
hiddenimports += hiddenimports_extra

