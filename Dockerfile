# crocket.dev. Classic builder only: Docker 29 on the VPS has no buildx.
# No syntax directive, no RUN --mount, no heredoc, no COPY --chmod.
#
# The build stage is crocket's published GCC 16.2 image. The runtime stage is
# Ubuntu 26.04 so glibc matches that image, plus GCC 16.2's libstdc++ on rpath.
# h2o is linked into the binary. OpenSSL and zlib stay dynamic.

FROM ghcr.io/sean3z/crocket-toolchain:gcc-16.2 AS build

ENV PATH=/opt/gcc-16.2/bin:$PATH

WORKDIR /src
COPY . /src

# Optional. version.hpp uses this when the fetch has no git metadata.
# Unset, the commit is the one FetchContent checks out for VERSION.
ARG CROCKET_GIT_COMMIT

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/* \
 && cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=/opt/gcc-16.2/bin/gcc-16.2 \
      -DCMAKE_CXX_COMPILER=/opt/gcc-16.2/bin/g++-16.2 \
      ${CROCKET_GIT_COMMIT:+-DCROCKET_GIT_COMMIT=${CROCKET_GIT_COMMIT}} \
 && cmake --build build --target crocket-site -j 2 \
 && mkdir -p /opt/export/bin /opt/export/lib \
 && install -m755 build/crocket-site /opt/export/bin/crocket-site \
 && strip --strip-unneeded /opt/export/bin/crocket-site \
 && cp -aL "$(/opt/gcc-16.2/bin/g++-16.2 -print-file-name=libstdc++.so.6)" /opt/export/lib/libstdc++.so.6 \
 && cp -aL "$(/opt/gcc-16.2/bin/g++-16.2 -print-file-name=libgcc_s.so.1)" /opt/export/lib/libgcc_s.so.1 \
 && LD_LIBRARY_PATH=/opt/export/lib ldd /opt/export/bin/crocket-site

FROM ubuntu:26.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
# libzstd is a NEEDED dependency of this binary (OpenSSL on Ubuntu 26.04).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libssl3 zlib1g libzstd1 ca-certificates \
 && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

COPY --from=build /opt/export/bin/crocket-site /usr/local/bin/crocket-site
COPY --from=build /opt/export/lib/ /usr/local/lib/crocket/

RUN useradd --no-log-init --uid 2000 --no-create-home --shell /usr/sbin/nologin crocket \
 && chmod 755 /usr/local/bin/crocket-site \
 && chmod 755 /usr/local/lib/crocket \
 && chmod 644 /usr/local/lib/crocket/*

USER 2000:2000
EXPOSE 8100
ENV CROCKET_PORT=8100
CMD ["crocket-site"]
