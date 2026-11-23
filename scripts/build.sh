#!/usr/bin/env bash
# Builds dist/hushfeed-<version>.zip from the extension/ folder (macOS / Linux).
set -e
cd "$(dirname "$0")/.."
VERSION=$(grep -m1 '"version"' extension/manifest.json | sed -E 's/.*: *"([^"]+)".*/\1/')
mkdir -p dist
rm -f "dist/hushfeed-$VERSION.zip"
(cd extension && zip -r "../dist/hushfeed-$VERSION.zip" . -x '.*' -x '*/.*')
echo "Created dist/hushfeed-$VERSION.zip"
