FROM aos-offline-indexed-sdk-1817:proof@sha256:0a6a90eb65ee9921e51943f54a89825dfe35a2a02b423b5d3c53f3f730184dec AS build
COPY native /build/native
RUN make -C /build/native with_llvm=no
FROM scratch
COPY --from=build /build/native/aos_admission_end.so /aos_admission_end.so
