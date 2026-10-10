FROM aos-precommit-probe-20261009-base:exact AS build
RUN apk add --no-cache build-base
COPY native /build/aos_admission_end
RUN make -C /build/aos_admission_end with_llvm=no
FROM aos-precommit-probe-20261009-base:exact
COPY --from=build /build/aos_admission_end/aos_admission_end.so /aos_admission_end.so
COPY --from=build /build/aos_admission_end/aos_admission_end.control /aos_admission_end.control
COPY --from=build /build/aos_admission_end/aos_admission_end--0.1.sql /aos_admission_end--0.1.sql
