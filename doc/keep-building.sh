#!/bin/bash
while true; do
    x=$(find source -mmin 0.1)
    if [[ "$x" != "" ]]; then
        make html
    fi
    sleep 2;
done
