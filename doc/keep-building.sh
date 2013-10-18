#!/bin/bash
while true; do
    x=$(find source -mtime -5s)
    if [[ "$x" != "" ]]; then 
        make html
    fi
    sleep 2;
done
