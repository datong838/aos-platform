FROM aos-pg-core-sdk-1779:exact@sha256:851765e2f8107a9014019a4431240db650318edf8cbd542f1e4514993581e992 AS build
COPY probe.c /build/clock-probe.c
RUN cc -Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared -I/usr/local/include/postgresql/server -I/usr/local/include/postgresql -o /build/clock-probe.so /build/clock-probe.c
FROM scratch
COPY --from=build /build/clock-probe.so /clock-probe.so
