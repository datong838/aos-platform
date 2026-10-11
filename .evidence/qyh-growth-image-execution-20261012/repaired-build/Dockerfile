FROM python:3.11-alpine
COPY aos_extension_sdk /usr/local/lib/python3.11/site-packages/aos_extension_sdk
COPY bundle /aos/bundle
COPY runtime.json runner.py /aos/
COPY wheelhouse /aos/wheelhouse
COPY runtime-requirements.txt /aos/runtime-requirements.txt
RUN python -m pip install --no-index --no-deps --require-hashes --find-links=/aos/wheelhouse -r /aos/runtime-requirements.txt
USER 65534:65534
