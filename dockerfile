FROM ubuntu:24.04

# Set non-interactive mode and configure timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# Install runtime + ops tooling only.
#
# Base image MUST be ubuntu:24.04 (GLIBC 2.39): pharos_cli / pharos_light are
# prebuilt in an ubuntu:24.04 + GCC13 container (v0.14.2+ toolchain) and require
# GLIBC >= 2.38. ubuntu:22.04 (GLIBC 2.35) cannot run them ("GLIBC_2.38 not found").
#
# No compiler is installed: the binaries are statically linked against
# libstdc++/libgcc, and docker-entrypoint.sh only copies them and execs
# pharos_light -- nothing is compiled on-image. Their only runtime NEEDED libs
# are libm/libc (base) + libz (zlib1g) + liblzma (liblzma5).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    vim \
    less \
    net-tools \
    procps \
    jq \
    tmux \
    pigz \
    tar \
    git \
    htop \
    telnet \
    netcat-openbsd \
    openssh-server \
    openssh-client \
    zlib1g \
    liblzma5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /data

# Copy binaries to /app/bin (includes pharos_cli, pharos_light, libevmone.so, VERSION)
COPY bin /app/bin

# Download ops tool from GitHub releases
RUN curl -L https://github.com/PharosNetwork/ops/releases/latest/download/ops-linux-amd64 -o /app/ops && \
    chmod +x /app/ops && \
    chmod +x /app/bin/*

# Copy startup script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expose ports
EXPOSE 18100 18200 19000 20000

CMD ["/app/docker-entrypoint.sh"]
