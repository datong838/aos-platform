FROM aos-precommit-probe-20261009-base:exact@sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883
COPY pack /opt/aos-native-package
COPY probe.sh /opt/aos-native-package/probe.sh
RUN mkdir /opt/aos-native-package-owned && cp /opt/aos-native-package/fb8771bcccb98d5919b5276b9137b1f694890c744a2017247bd977930d020626.bin /opt/aos-native-package-owned/fixture.bin && chown 501:20 /opt/aos-native-package-owned/fixture.bin && chmod 444 /opt/aos-native-package-owned/fixture.bin
USER 501:20
ENTRYPOINT ["/bin/sh","/opt/aos-native-package/probe.sh"]
