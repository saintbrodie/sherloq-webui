#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TRUFOR_REPOSITORY = "https://github.com/grip-unina/TruFor.git"
TRUFOR_WEIGHTS_URL = "https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip"
TRUFOR_WEIGHTS_ZIP_MD5 = "7bee48f3476c75616c3c5721ab256ff8"
LICENSE_URL = "https://github.com/grip-unina/TruFor/blob/main/test_docker/LICENSE.txt"


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Clone the official GRIP-UNINA TruFor repository and download the official "
            "inference-weight archive used by Sherloq's optional TruFor worker."
        )
    )
    parser.add_argument("--target", default="TruFor", help="Destination for the official TruFor checkout")
    parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Confirm that you have read and accept the upstream informational/nonprofit-use license",
    )
    args = parser.parse_args()

    if not args.accept_license:
        print("TruFor is distributed under GRIP-UNINA's informational/nonprofit-use license.", file=sys.stderr)
        print(f"Review: {LICENSE_URL}", file=sys.stderr)
        print("Re-run with --accept-license only if those terms are acceptable.", file=sys.stderr)
        return 2

    target = Path(args.target).expanduser().resolve()
    if not target.exists():
        subprocess.run(["git", "clone", "--depth", "1", TRUFOR_REPOSITORY, str(target)], check=True)
    elif not (target / ".git").exists():
        raise SystemExit(f"Target exists but is not a Git checkout: {target}")

    test_docker = target / "test_docker"
    license_file = test_docker / "LICENSE.txt"
    if not license_file.is_file():
        raise SystemExit(f"Official TruFor test_docker tree is missing: {test_docker}")

    weight_file = test_docker / "weights" / "trufor.pth.tar"
    if weight_file.is_file():
        print(f"TruFor weights already present: {weight_file}")
        return 0

    with tempfile.TemporaryDirectory(prefix="sherloq-trufor-setup-") as temporary:
        archive = Path(temporary) / "TruFor_weights.zip"
        print(f"Downloading official weights from {TRUFOR_WEIGHTS_URL}")
        urllib.request.urlretrieve(TRUFOR_WEIGHTS_URL, archive)
        observed = md5(archive)
        if observed.lower() != TRUFOR_WEIGHTS_ZIP_MD5:
            raise SystemExit(
                "TruFor weight archive checksum mismatch: "
                f"expected {TRUFOR_WEIGHTS_ZIP_MD5}, got {observed}"
            )
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(test_docker)

    if not weight_file.is_file():
        raise SystemExit(
            "The official archive passed its documented MD5 but did not create the expected "
            f"weight file: {weight_file}"
        )

    print(f"TruFor checkout ready: {target}")
    print(f"Weights: {weight_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
