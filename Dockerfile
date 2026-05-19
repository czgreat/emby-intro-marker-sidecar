FROM m.daocloud.io/docker.io/library/python:3.12-slim

ARG HTTP_PROXY_FALLBACK=
ARG HTTPS_PROXY_FALLBACK=
ARG ALL_PROXY_FALLBACK=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    (apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update && \
     apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 install -y --no-install-recommends \
        ffmpeg \
        wget \
        sqlite3 \
        tini \
        libchromaprint-tools) || \
    (export http_proxy="${HTTP_PROXY_FALLBACK}" https_proxy="${HTTPS_PROXY_FALLBACK}" all_proxy="${ALL_PROXY_FALLBACK}"; \
     apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update && \
     apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 install -y --no-install-recommends \
        ffmpeg \
        wget \
        sqlite3 \
        tini \
        libchromaprint-tools); \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN set -eux; \
    (python -m pip install \
        --default-timeout=15 \
        --retries=1 \
        -i https://mirrors.aliyun.com/pypi/simple \
        -r /app/requirements.txt) || \
    (export http_proxy="${HTTP_PROXY_FALLBACK}" https_proxy="${HTTPS_PROXY_FALLBACK}" all_proxy="${ALL_PROXY_FALLBACK}"; \
     python -m pip install \
        --default-timeout=15 \
        --retries=1 \
        -i https://pypi.org/simple \
        -r /app/requirements.txt)

COPY app /app/app
COPY config /app/config

RUN mkdir -p \
    /var/lib/intro-marker/cache \
    /var/lib/intro-marker/work \
    /var/log/intro-marker

ENTRYPOINT ["/usr/bin/tini", "--"]
