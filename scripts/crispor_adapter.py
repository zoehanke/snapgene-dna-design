# -*- coding: utf-8 -*-
"""crispor_adapter.py - CRISPOR external adapter skeleton.

No CRISPOR source code, binaries, models or third-party credentials are
bundled. This adapter only detects a local installation, captures version and
license notice, and can later submit a query only after explicit per-upload
consent via ``sequence_upload_consent``.
"""
import json
import pathlib
import sys

from provenance import source
from sequence_upload_consent import SequenceUploadConsent


CRISPOR_URL = "https://crispor.org"
CRISPOR_LICENSE_URL = ("https://github.com/maximilianh/crisporWebsite/"
                       "blob/master/LICENSE.txt")


def detect(executable=None):
    # v0.8-dev1 does not implement local CRISPOR execution. We probe common
    # local command names and report unavailable when none exists.
    import shutil
    found = None
    for name in (executable, "crispor", "crispor.py"):
        if name and shutil.which(name):
            found = name
            break
    version = None
    verification = {"method": "path-probe",
                    "status": "verified" if found else "unavailable"}
    return {
        "installed": bool(found),
        "executable": found,
        "version": version,
        "license_notice": {
            "url": CRISPOR_LICENSE_URL,
            "status": "user-must-review",
        },
        "provenance": [source(
            "software", "CRISPOR", "guide-design-and-off-target-analysis",
            url="https://github.com/maximilianh/crisporWebsite",
            version=version, status=verification["status"],
            verification=verification)],
    }


def online_query_request(target_sequence, organism, purpose):
    """Build a consent request. Does NOT upload anything."""
    consent = SequenceUploadConsent("target-region")
    consent.request(CRISPOR_URL, purpose, sequence=target_sequence,
                    retention_notice=True)
    return consent


if __name__ == "__main__":
    print(json.dumps(detect(), ensure_ascii=False, indent=2))
    sys.exit(0)
