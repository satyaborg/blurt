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

git tag "$tag"
git push origin "$tag"
echo "Pushed $tag — PyPI publish will start shortly."
