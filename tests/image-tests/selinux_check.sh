#!/bin/bash

set -uo pipefail

STATUS=$(sestatus | awk -F ':' '/SELinux status/ { gsub(" ",""); print $2}')
CURRENT_MODE=$(sestatus | awk -F ':' '/Current mode/ { gsub(" ",""); print $2}')
MODE_FROM_CFG=$(sestatus | awk -F ':' '/Mode from config file/ { gsub(" ",""); print $2}')

echo "[selinux] Checking SELinux status..."

# Check selinux status
if [ "$STATUS" != "enabled" ]; then
   echo "[selinux] FAIL: Selinux is ${STATUS}, it is not enabled on this system!"
   echo "[selinux] FAIL: $(basename "$0" .sh)"
   exit 1
else
   echo "[selinux] PASS: Selinux is ${STATUS} on this system."

   # Compared current mode and mode from config file
   if [ "$CURRENT_MODE" == "$MODE_FROM_CFG" ]; then
      echo "[selinux] INFO: Selinux current mode is the same as the mode from config file."

      if [ "$CURRENT_MODE" == "enforcing" ] && [ "$MODE_FROM_CFG" == "enforcing" ]; then
         echo "[selinux] PASS: Both of the modes are Enforcing."
         echo "[selinux] PASS: $(basename "$0" .sh)"
         exit 0
      else
         echo "[selinux] INFO: Selinux current mode is: ${CURRENT_MODE}."
         echo "[selinux] INFO: The mode from config file is: ${MODE_FROM_CFG}."
         echo "[selinux] FAIL: Either current mode or config file mode is NOT set to enforcing."
         echo "[selinux] FAIL: $(basename "$0" .sh)"
         exit 1
      fi
   else
      echo "[selinux] INFO: Selinux current mode is: ${CURRENT_MODE}."
      echo "[selinux] INFO: The mode from config file is: ${MODE_FROM_CFG}."
      echo "[selinux] FAIL: These modes are different!"
      echo "[selinux] FAIL: $(basename "$0" .sh)"
      exit 1
   fi
fi
