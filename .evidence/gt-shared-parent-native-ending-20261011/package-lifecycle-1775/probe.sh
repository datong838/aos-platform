#!/bin/sh
# Dedicated isolated byte fixtures only. Never a PostgreSQL or Root installer.
set -eu
mode="$1"
cd /opt/aos-native-package
sha256sum -c SHA256SUMS >/dev/null
owned=/opt/aos-native-package-owned/fixture.bin
first=$(sed -n '1s/.*  //p' SHA256SUMS)
if [ "$mode" = mutable ]; then
    if printf X >> "$owned" 2>/dev/null; then
        echo INITIAL_MODE444_DENIAL_MISSING; exit 20
    fi
    chmod u+w "$owned"
    printf X >> "$owned"
    echo OWNER_CHMOD_THEN_WRITE_SUCCEEDED
else
    for file in "$owned" "/opt/aos-native-package/$first"; do
        if printf X >> "$file" 2>/dev/null; then echo PROTECTED_WRITE_SUCCEEDED; exit 21; fi
        if chmod u+w "$file" 2>/dev/null; then echo PROTECTED_CHMOD_SUCCEEDED; exit 22; fi
        if mv "$file" "$file.replaced" 2>/dev/null; then echo PROTECTED_RENAME_SUCCEEDED; exit 23; fi
    done
    echo OWNER_AND_PACKAGE_WRITE_CHMOD_RENAME_DENIED
fi
sha256sum -c SHA256SUMS >/dev/null
id
echo PACKAGE27_HASHES_UNCHANGED
