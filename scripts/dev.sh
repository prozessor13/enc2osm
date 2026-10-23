#!/bin/sh
# Run a command inside the project image with the working tree mounted.
# Usage: scripts/dev.sh pytest -q   |   scripts/dev.sh python -m enc2osm inventory fixtures/small
set -e
cd "$(dirname "$0")/.."
IMAGE=${ENC2OSM_IMAGE:-enc2osm:dev}
exec docker run --rm -i -v "$PWD":/src -w /src -e PYTHONPATH=/src \
  --entrypoint "" "$IMAGE" "$@"
