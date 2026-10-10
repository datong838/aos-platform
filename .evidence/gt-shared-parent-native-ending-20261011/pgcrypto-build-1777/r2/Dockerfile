FROM aos-precommit-probe-20261009-base:exact@sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883 AS build
RUN apk add --no-cache build-base openssl-dev zlib-dev
COPY frozen-source /build/pgcrypto
RUN make -C /build/pgcrypto USE_PGXS=1 with_llvm=no && pg_config --version && apk info -v libcrypto3 openssl-dev zlib-dev && cc --version
FROM aos-precommit-probe-20261009-base:exact@sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883
COPY --from=build /build/pgcrypto/pgcrypto.so /artifacts/pgcrypto.so
COPY --from=build /build/pgcrypto/pgcrypto.control /artifacts/pgcrypto.control
