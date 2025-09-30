#!/usr/bin/bash

git ls-files -c -z \
    | xargs -0 awk -vORS='\0' 'FNR==1 && /^#!.*sh/ { print FILENAME }' \
    | xargs -0r shellcheck --severity=warning
