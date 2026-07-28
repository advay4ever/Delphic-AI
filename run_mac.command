#!/bin/zsh
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  python3 run_app.py
else
  echo "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/"
fi

echo
echo "Press any key to close this window."
read -k 1
