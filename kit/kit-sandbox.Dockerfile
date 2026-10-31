FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/mpl \
    XDG_CACHE_HOME=/tmp

# KIT gets a useful, vetted toolbox baked into the image. Packages are installed
# at BUILD time only; the runtime container has no network and no package
# manager path that can pull anything new.
RUN pip install --no-cache-dir \
    numpy==2.3.4 \
    pandas==2.3.3 \
    matplotlib==3.10.7 \
    Pillow==12.0.0 \
    scipy==1.16.3 \
    sympy==1.14.0 \
    networkx==3.5

# A non-root user already exists as nobody (65534). The image is run with
# --read-only and a tmpfs at /tmp, so nothing in this image is writable.
WORKDIR /tmp
