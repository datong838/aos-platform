FROM aos-precommit-probe-20261009-base:exact AS build
RUN apk add --no-cache build-base
COPY probe.c /build/probe.c
RUN cc -Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared -I$(pg_config --includedir-server) -I$(pg_config --includedir) -o /build/aos_postdrain_probe_1745.so /build/probe.c
FROM aos-precommit-probe-20261009-base:exact
COPY --from=build /build/aos_postdrain_probe_1745.so /aos_postdrain_probe_1745.so
