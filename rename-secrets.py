#!/usr/bin/env python3

# You can use this script to rename all your secrets files to the new
# .gpg suffix. This is necessary because the new version of batou
# detects the secret provider based on the file suffix.

import glob
import os
import shutil
import sys


def main():
    """
    in cwd, renames all files in environments/*/secrets.cfg to environments/*/secrets.cfg.gpg
    as well as all files in environments/*/secret-* without .age or .gpg suffix to secret-*.gpg
    """

    for path in glob.glob("environments/*/secrets.cfg"):
        print("Renaming", path)
        shutil.move(path, path + ".gpg")
    for path in glob.glob("environments/*/secret-*"):
        if not path.endswith(".age") and not path.endswith(".gpg"):
            print("Renaming", path)
            shutil.move(path, path + ".gpg")


if __name__ == "__main__":
    sys.exit(main())
