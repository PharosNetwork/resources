FROM ubuntu:22.04

# Set non-interactive mode and configure timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# Install dependencies and common tools
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
    gcc-12 \
    g++-12 \
    make \
    tar \
    git \
    htop \
    telnet \
    netcat \
    openssh-server \
    openssh-client \
    libssl-dev \
    libbz2-dev \
    libffi-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Make gcc-12/g++-12 the default toolchain for on-image compilation.
# The runtime image compiles user-supplied sources on demand; align its
# default compiler with the upgraded build toolchain (was gcc-11, the
# ubuntu:22.04 default, before this change).
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 100

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
