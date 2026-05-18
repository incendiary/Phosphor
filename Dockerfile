# ============================================================
# Stage 1: Build patched x3270 / s3270 binaries from source
# ============================================================
# Phosphor requires a patched build of suite3270 3.6ga4 that removes
# field-protection checks, allowing it to interact with protected screen
# fields. The patch is applied before compilation.
FROM ubuntu:24.04 AS suite3270builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    build-essential \
    automake \
    libxt-dev \
    libxmu-headers \
    xfonts-utils \
    libxaw7-dev \
    libncurses-dev \
    tclsh \
    tcl8.6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN wget -q \
    "https://sourceforge.net/projects/x3270/files/x3270/3.6ga4/suite3270-3.6ga4-src.tgz/download" \
    -O suite3270.tgz \
    && tar xzf suite3270.tgz

WORKDIR /build/suite3270-3.6

COPY suite3270-full.patch .

RUN patch -p1 < suite3270-full.patch \
    && ./configure --enable-static \
    && make \
    && make install


# ============================================================
# Stage 2: Phosphor runtime image
# ============================================================
FROM ubuntu:24.04

LABEL org.opencontainers.image.title="Phosphor"
LABEL org.opencontainers.image.description="Mainframe TN3270 security assessment tool"
LABEL org.opencontainers.image.source="https://github.com/incendiary/Phosphor"
LABEL org.opencontainers.image.licenses="GPL-2.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy patched binaries from builder stage
COPY --from=suite3270builder /usr/local/bin/s3270 /app/lin_Binaries/s3270
COPY --from=suite3270builder /usr/local/bin/x3270 /app/lin_Binaries/x3270

# Install Python dependencies before copying source so this layer is cached
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Phosphor runs headless (s3270) by default inside Docker.
# Pass -v True only if you have an X11 server available and have mounted
# /tmp/.X11-unix into the container.
ENTRYPOINT ["python3", "phosphor.py"]
