FROM aos-pg-core-sdk-1779:exact@sha256:851765e2f8107a9014019a4431240db650318edf8cbd542f1e4514993581e992 AS probe
COPY relink.py reference.json /probe/
RUN python3 /probe/relink.py
FROM scratch
COPY --from=probe /probe-output /artifacts
