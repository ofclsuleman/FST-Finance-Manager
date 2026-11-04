#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
python3 -m pip install --upgrade pyinstaller || exit 1
python3 -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name "FST - Finance Management" \
  --add-data "assets:assets" \
  fst_finance.py || exit 1
echo "Build complete: dist/FST - Finance Management"
