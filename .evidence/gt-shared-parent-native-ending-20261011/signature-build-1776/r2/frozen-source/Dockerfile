# Isolated build profile only; no default compose/deployment integration.
ARG PG_BASE_IMAGE
FROM ${PG_BASE_IMAGE} AS build
RUN apk add --no-cache build-base openssl-dev
WORKDIR /build
COPY aos_ed25519.c Makefile aos_ed25519.control aos_ed25519--1.0.sql ./
RUN make with_llvm=no && make with_llvm=no install DESTDIR=/stage \
    && pg_config --version && apk info -v libcrypto3 openssl-dev && cc --version

FROM ${PG_BASE_IMAGE}
COPY --from=build /stage/usr/local/lib/postgresql/aos_ed25519.so /usr/local/lib/postgresql/
COPY --from=build /stage/usr/local/share/postgresql/extension/aos_ed25519* /usr/local/share/postgresql/extension/
