#!/bin/zsh
set -euo pipefail

release_version=${1:-0.1.8}
script_dir=${0:A:h}
project_dir=${script_dir:h}
output_dir=${2:-"$project_dir/dist"}
archive_name="Delphic-AI-v${release_version}-macOS-Python.zip"
staging_root=$(mktemp -d "${TMPDIR:-/tmp}/delphic-mac-source.XXXXXX")
package_dir="$staging_root/Delphic AI"

cleanup() {
  rm -rf "$staging_root"
}
trap cleanup EXIT

mkdir -p "$package_dir/ai" "$package_dir/static" "$package_dir/templates"

cp "$project_dir/.env.example" "$package_dir/.env.example"
cp "$project_dir/app.py" "$package_dir/app.py"
cp "$project_dir/database.py" "$package_dir/database.py"
cp "$project_dir/requirements.txt" "$package_dir/requirements.txt"
cp "$project_dir/run_app.py" "$package_dir/run_app.py"
cp "$project_dir/run_mac.command" "$package_dir/run_mac.command"
cp "$project_dir/MAC_LAUNCHER_README.md" "$package_dir/README.md"
cp -R "$project_dir/ai/." "$package_dir/ai/"
cp -R "$project_dir/static/." "$package_dir/static/"
cp -R "$project_dir/templates/." "$package_dir/templates/"
chmod 755 "$package_dir/run_mac.command"

if find "$package_dir" \( -name ".env" -o -name "chat_history.db" \) -print -quit | grep -q .; then
  echo "Private data was found in the Mac source package." >&2
  exit 1
fi

mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
if [[ -e "$output_dir/$archive_name" || -e "$output_dir/$archive_name.sha256" ]]; then
  echo "Release files already exist in $output_dir" >&2
  exit 1
fi

(
  cd "$staging_root"
  COPYFILE_DISABLE=1 zip -q -r -X "$output_dir/$archive_name" "Delphic AI"
)
(
  cd "$output_dir"
  shasum -a 256 "$archive_name" > "$archive_name.sha256"
)

echo "Created:"
echo "$output_dir/$archive_name"
echo "$output_dir/$archive_name.sha256"
