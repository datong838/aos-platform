FROM aos-precommit-probe-20261009-base:exact AS build
RUN apk add --no-cache build-base
COPY probe.c /build/probe.c
RUN cc -Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared -I$(pg_config --includedir-server) -I$(pg_config --includedir) -o /build/probe.so /build/probe.c
FROM scratch
COPY --from=build /build/probe.so /probe.so
