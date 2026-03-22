FROM --platform=linux/amd64 ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget fakeroot rsync pv bsdmainutils ca-certificates \
    openssl xz-utils make curl build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN wget -q https://github.com/qnap-dev/QDK/releases/download/v2.5.0/qdk_2.5.0_amd64.deb \
    && dpkg -i --force-depends qdk_2.5.0_amd64.deb \
    && rm -f qdk_2.5.0_amd64.deb
WORKDIR /work
ENTRYPOINT ["qbuild"]
