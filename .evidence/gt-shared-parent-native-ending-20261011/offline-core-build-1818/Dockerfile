FROM aos-offline-indexed-sdk-1817:proof@sha256:0a6a90eb65ee9921e51943f54a89825dfe35a2a02b423b5d3c53f3f730184dec AS build
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
