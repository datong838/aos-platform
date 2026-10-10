FROM aos-precommit-probe-20261009-base:exact@sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883 AS build
RUN apk add --no-cache llvm21-dev clang21 bison coreutils dpkg-dev dpkg flex g++ gcc krb5-dev libc-dev libedit-dev libxml2-dev libxslt-dev linux-headers make openldap-dev openssl-dev perl-dev perl-ipc-run perl-utils python3-dev tcl-dev util-linux-dev zlib-dev icu-dev lz4-dev zstd-dev
WORKDIR /build
COPY postgresql-16.14.tar.bz2 configure-flags.json build.py ./
RUN python3 /build/build.py
FROM scratch
COPY --from=build /build/source/postgresql-16.14/src/backend/postgres /artifacts/postgres
COPY --from=build /build/source/postgresql-16.14/src/pl/plpgsql/src/plpgsql.so /artifacts/plpgsql.so
COPY --from=build /build/source/postgresql-16.14/contrib/pgcrypto/pgcrypto.so /artifacts/pgcrypto.so
COPY --from=build /build/source/postgresql-16.14/src/include/pg_config.h /artifacts/pg_config.h
COPY --from=build /build/source/postgresql-16.14/src/include/pg_config_ext.h /artifacts/pg_config_ext.h
COPY --from=build /build/source/postgresql-16.14/src/include/utils/probes.h /artifacts/probes.h
