#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
project_dir=${script_dir:h}
version_file="$project_dir/VERSION"
python_bin=${DELPHIC_BUILD_PYTHON:-"$project_dir/.venv/bin/python"}
output_dir=${DELPHIC_RELEASE_DIR:-"$project_dir/dist"}
smoke_port=${DELPHIC_SMOKE_PORT:-51273}
smoke_pid=""
staging_dir=""
smoke_dir=""

cleanup() {
  if [[ -n "$smoke_pid" ]] && kill -0 "$smoke_pid" 2>/dev/null; then
    kill "$smoke_pid" 2>/dev/null || true
    wait "$smoke_pid" 2>/dev/null || true
  fi
  [[ -z "$staging_dir" ]] || rm -rf "$staging_dir"
  [[ -z "$smoke_dir" ]] || rm -rf "$smoke_dir"
}
trap cleanup EXIT

if [[ $OSTYPE != darwin* ]]; then
  echo "The Mac release must be built on macOS." >&2
  exit 1
fi
if [[ ! -f "$version_file" ]]; then
  echo "VERSION was not found." >&2
  exit 1
fi

app_version=$(tr -d '[:space:]' < "$version_file")
if [[ ! $app_version =~ '^[0-9]+\.[0-9]+\.[0-9]+$' ]]; then
  echo "VERSION must look like 1.2.3." >&2
  exit 1
fi
if [[ ! -x "$python_bin" ]]; then
  echo "Build Python was not found at $python_bin" >&2
  echo "Create .venv and install requirements-build.txt first." >&2
  exit 1
fi

for command_name in curl hdiutil; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$command_name is required to build the Mac release." >&2
    exit 1
  fi
done

cd "$project_dir"

if [[ ${DELPHIC_SKIP_TESTS:-false} != true ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to run the browser tests." >&2
    exit 1
  fi
  echo "Running Python tests..."
  "$python_bin" -m pytest -q
  echo "Running browser tests..."
  DELPHIC_TEST_PORT=${DELPHIC_TEST_PORT:-5004} npm run test:e2e
fi

echo "Checking PyInstaller..."
"$python_bin" -c 'import PyInstaller' || {
  echo "Install requirements-build.txt in the build environment." >&2
  exit 1
}

mkdir -p "$output_dir"
output_dir=${output_dir:A}
app_path="$output_dir/Delphic AI.app"

echo "Building Delphic AI $app_version..."
"$python_bin" -m PyInstaller --clean --noconfirm --distpath "$output_dir" --workpath "$project_dir/build/mac-release" "$project_dir/delphic_desktop.spec"

if [[ ! -d "$app_path" ]]; then
  echo "PyInstaller did not create $app_path" >&2
  exit 1
fi
if find "$app_path" \( -name '.env' -o -name 'chat_history.db' \) -print -quit | grep -q .; then
  echo "Private settings or chat data entered the app bundle." >&2
  exit 1
fi

if [[ -n ${DELPHIC_CODESIGN_IDENTITY:-} ]]; then
  codesign --verify --deep --strict --verbose=2 "$app_path"
else
  echo "Building an unsigned test release. Set DELPHIC_CODESIGN_IDENTITY for a public release."
fi

echo "Smoke-testing the packaged app..."
smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/delphic-mac-smoke.XXXXXX")
smoke_log="$smoke_dir/delphic.log"
DELPHIC_DATA_DIR="$smoke_dir/data" \
DELPHIC_OPEN_BROWSER=false \
DELPHIC_HEADLESS=true \
PORT="$smoke_port" \
"$app_path/Contents/MacOS/Delphic AI" >"$smoke_log" 2>&1 &
smoke_pid=$!

ready=false
math_page="$smoke_dir/math.html"
science_page="$smoke_dir/science.html"
for _attempt in {1..90}; do
  if ! kill -0 "$smoke_pid" 2>/dev/null; then
    echo "The packaged app stopped during its smoke test." >&2
    cat "$smoke_log" >&2
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:$smoke_port/" -o "$math_page" 2>/dev/null && \
     curl -fsS "http://127.0.0.1:$smoke_port/science" -o "$science_page" 2>/dev/null && \
     grep -Fq "Version $app_version" "$math_page" && \
     grep -Fq "Version $app_version" "$science_page" && \
     curl -fsS "http://127.0.0.1:$smoke_port/static/graphing.js" >/dev/null 2>&1 && \
     curl -fsS "http://127.0.0.1:$smoke_port/static/science-diagrams.js" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ $ready != true ]]; then
  echo "The packaged app did not serve its Math and Science pages." >&2
  cat "$smoke_log" >&2
  exit 1
fi
kill "$smoke_pid" 2>/dev/null || true
wait "$smoke_pid" 2>/dev/null || true
smoke_pid=""

"$python_bin" "$project_dir/scripts/check_packaged_library.py" \
  --executable "$app_path/Contents/MacOS/Delphic AI" --port "$smoke_port"

staging_dir=$(mktemp -d "${TMPDIR:-/tmp}/delphic-mac-dmg.XXXXXX")
cp -R "$app_path" "$staging_dir/Delphic AI.app"
ln -s /Applications "$staging_dir/Applications"

release_kind="unsigned"
if [[ -n ${DELPHIC_CODESIGN_IDENTITY:-} ]]; then
  release_kind="signed"
fi
dmg_name="Delphic-AI-v$app_version-macOS-$release_kind.dmg"
dmg_path="$output_dir/$dmg_name"
rm -f "$dmg_path" "$dmg_path.sha256"

echo "Creating $dmg_name..."
hdiutil create \
  -quiet \
  -volname "Delphic AI $app_version" \
  -srcfolder "$staging_dir" \
  -ov \
  -format UDZO \
  "$dmg_path"

if [[ -n ${DELPHIC_CODESIGN_IDENTITY:-} ]]; then
  codesign --force --sign "$DELPHIC_CODESIGN_IDENTITY" "$dmg_path"
fi
if [[ -n ${DELPHIC_NOTARY_PROFILE:-} ]]; then
  if [[ -z ${DELPHIC_CODESIGN_IDENTITY:-} ]]; then
    echo "DELPHIC_NOTARY_PROFILE requires DELPHIC_CODESIGN_IDENTITY." >&2
    exit 1
  fi
  xcrun notarytool submit "$dmg_path" --keychain-profile "$DELPHIC_NOTARY_PROFILE" --wait
  xcrun stapler staple "$dmg_path"
  xcrun stapler validate "$dmg_path"
fi

(
  cd "$output_dir"
  shasum -a 256 "$dmg_name" > "$dmg_name.sha256"
)

echo "Created:"
echo "$app_path"
echo "$dmg_path"
echo "$dmg_path.sha256"
