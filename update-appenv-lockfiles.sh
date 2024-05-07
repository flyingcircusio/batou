#!/bin/sh

base=$PWD
# for each folder in base with a requirements.lock file, go to that folder and run `./appenv update-lockfile`
for folder in $(find $base -name requirements.lock | xargs dirname); do
    # only if path does not contain a '.'
    if [[ $folder == *"."* ]]; then
        continue
    fi
    cd $folder
    echo "Updating lockfile in $folder"
    ./appenv update-lockfile
done
