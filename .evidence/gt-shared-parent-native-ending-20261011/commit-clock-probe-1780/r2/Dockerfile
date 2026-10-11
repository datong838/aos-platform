FROM aos-pg-core-sdk-1779:exact@sha256:e2b64beaa905db2b8519bf667e40309647f440d168bb0241639e118c64714f0e AS build
COPY probe.c /build/clock-probe.c
RUN cc -Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared -I/usr/local/include/postgresql/server -I/usr/local/include/postgresql -o /build/clock-probe.so /build/clock-probe.c
FROM scratch
COPY --from=build /build/clock-probe.so /clock-probe.so
