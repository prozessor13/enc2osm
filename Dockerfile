# Pinned GDAL base (multi-arch: amd64 + arm64). Tag ubuntu-small-3.13.3.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.13.3@sha256:64250faf833c06d4b21afce4c27190039ba7ab58d70f0eebc87cf77d929c0b40

# pyosmium from the distro (matches libosmium of the base); osmium-tool and
# pytest/PyYAML (cross-check of the stdlib YAML loader) are dev/validation tools only,
# not runtime dependencies of enc2osm.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-pyosmium=4.3.0-1build1 \
      python3-venv python3-pip \
      osmium-tool=1.19.0-1build1 \
      python3-pytest python3-yaml \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir ruff==0.14.1
ENV PATH=/opt/venv/bin:$PATH

COPY pyproject.toml README.md LICENSE /src/
COPY enc2osm /src/enc2osm
RUN pip install --no-cache-dir --no-deps /src

WORKDIR /work
ENTRYPOINT ["enc2osm"]
