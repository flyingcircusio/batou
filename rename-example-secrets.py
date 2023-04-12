#!/usr/bin/env python3
# renames all ./example/*/environments/*/secrets.cfg to ./example/*/environments/*/secrets.cfg.gpg

import os
import shutil
import sys


def main():
    for root, dirs, files in os.walk("."):
        for file in files:
            if file == "secrets.cfg":
                path = os.path.join(root, file)
                print("Renaming", path)
                shutil.move(path, path + ".gpg")


if __name__ == "__main__":
    sys.exit(main())
