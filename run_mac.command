#!/bin/zsh
script_dir=${0:A:h}
cd "$script_dir" || exit 1

finish() {
  launcher_status=$1
  echo
  printf "Press Return to close this window."
  read -r
  exit "$launcher_status"
}

echo "Starting Delphic AI..."
echo

if command -v python3 >/dev/null 2>&1; then
  if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    python_version=$(python3 --version 2>&1)
    echo "Delphic AI needs Python 3.10 or newer."
    echo "This Mac is using: $python_version"
    echo "Download Python from https://www.python.org/downloads/"
    open "https://www.python.org/downloads/" >/dev/null 2>&1
    finish 1
  fi
else
  echo "Python 3.10 or newer is required."
  echo "Download Python from https://www.python.org/downloads/"
  open "https://www.python.org/downloads/" >/dev/null 2>&1
  finish 1
fi

echo "The first start may take a few minutes while packages install."
echo "Keep this Terminal window open while using Delphic AI."
echo

python3 run_app.py
launcher_status=$?

if (( launcher_status != 0 )); then
  echo
  echo "Delphic AI stopped with an error."
  echo "Read the message above, then try opening run_mac.command again."
fi

finish "$launcher_status"
