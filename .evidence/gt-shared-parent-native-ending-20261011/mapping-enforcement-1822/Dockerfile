FROM aos-offline-indexed-sdk-1817:proof@sha256:0a6a90eb65ee9921e51943f54a89825dfe35a2a02b423b5d3c53f3f730184dec AS build
COPY probe.c /probe.c
RUN gcc -Wall -Wextra -Werror -static -O2 /probe.c -o /probe
FROM scratch
COPY --from=build /probe /probe
USER 501:20
ENTRYPOINT ["/probe"]
