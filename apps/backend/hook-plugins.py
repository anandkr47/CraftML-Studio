"""
PyInstaller hook for plugins package
Ensures all plugin submodules are properly collected
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all submodules from plugins package
hiddenimports = collect_submodules('plugins')

# Also collect data files if any
datas, binaries, hiddenimports_extra = collect_all('plugins')
hiddenimports += hiddenimports_extra

