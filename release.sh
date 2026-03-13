#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "Usage: ./release.sh <version>  (e.g. ./release.sh 0.2.0)"
  exit 1
fi

tag="v$1"

if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "Tag $tag already exists."
  exit 1
fi

git-cliff --tag "$tag" --output CHANGELOG.md
git add CHANGELOG.md
git commit -m "changelog $tag"

git tag "$tag"
git push origin main --tags
echo "Pushed $tag — PyPI publish will start shortly."

# Update Homebrew tap
TAP_DIR="${TAP_DIR:-../homebrew-blurt}"
if [ -d "$TAP_DIR" ]; then
  new_sha=$(curl -sL "https://github.com/satyaborg/blurt/archive/refs/tags/$tag.tar.gz" | shasum -a 256 | cut -d' ' -f1)
  sed -i '' "s|/tags/v[0-9.]*\.tar\.gz|/tags/$tag.tar.gz|" "$TAP_DIR/Formula/blurt.rb"
  sed -i '' "s/sha256 \"[a-f0-9]*\"/sha256 \"$new_sha\"/" "$TAP_DIR/Formula/blurt.rb"
  sed -i '' "s/blurt==[0-9.]*/blurt==$1/" "$TAP_DIR/Formula/blurt.rb"
  (cd "$TAP_DIR" && git add -A && git commit -m "blurt $tag" && git push origin main)
  echo "Homebrew tap updated."
else
  echo "Warning: $TAP_DIR not found, skipping tap update."
fi
