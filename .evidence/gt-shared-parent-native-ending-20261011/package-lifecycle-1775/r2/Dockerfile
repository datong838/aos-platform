FROM aos-precommit-probe-20261009-base:exact@sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883 AS substrate
FROM scratch
COPY --from=substrate /bin/busybox /bin/busybox
COPY --from=substrate /lib/ld-musl-aarch64.so.1 /lib/ld-musl-aarch64.so.1
COPY pack /opt/aos-native-package
COPY probe.sh /opt/aos-native-package/probe.sh
RUN ["/bin/busybox","sh","-c","/bin/busybox ln -s ld-musl-aarch64.so.1 /lib/libc.musl-aarch64.so.1; for c in sh sha256sum sed chmod id mv; do /bin/busybox ln -s busybox /bin/$c; done; /bin/busybox mkdir /opt/aos-native-package-owned; /bin/busybox cp /opt/aos-native-package/fb8771bcccb98d5919b5276b9137b1f694890c744a2017247bd977930d020626.bin /opt/aos-native-package-owned/fixture.bin; /bin/busybox chown 501:20 /opt/aos-native-package-owned/fixture.bin; /bin/busybox chmod 444 /opt/aos-native-package-owned/fixture.bin"]
USER 501:20
ENTRYPOINT ["/bin/sh","/opt/aos-native-package/probe.sh"]
