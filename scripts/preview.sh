#!/bin/sh
# Build the small fixture (San Francisco, 14 cells) into out/preview/enc-sf.osm.pbf.
#
#   scripts/preview.sh                      # build only
#   SEAMAP_DIR=~/src/seamap scripts/preview.sh   # build + render with the SeaMap pipeline
#
# The SeaMap pipeline (openwatersio/seamap) reads data/<area>.osm.pbf; the file is copied there
# as data/enc-sf.osm.pbf and rendered with `bin/run --area=enc-sf --download=false --force`
# (output: data/seamarks.pmtiles, open it with the repo's viewer).
set -e
cd "$(dirname "$0")/.."
IMAGE=${ENC2OSM_IMAGE:-enc2osm:dev}
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" .
mkdir -p out/preview
docker run --rm -v "$PWD":/work -w /work "$IMAGE" build \
  -o out/preview/enc-sf.osm.pbf --classes v2 --report out/preview/report --workers 4 \
  tests/data/small
echo "written: out/preview/enc-sf.osm.pbf (reports in out/preview/report)"
if [ -n "$SEAMAP_DIR" ]; then
  cp out/preview/enc-sf.osm.pbf "$SEAMAP_DIR/data/enc-sf.osm.pbf"
  (cd "$SEAMAP_DIR" && DEPTH_URL=none bin/run --area=enc-sf --download=false --force)
fi
