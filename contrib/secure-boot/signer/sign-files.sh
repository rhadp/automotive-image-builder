#!/usr/bin/bash

set -euo pipefail

usage() {
    echo "Usage: $0 [--certificates CERTS] [--nickname NICKNAME] [--password-file PASSWORD_FILE] [FILE1] [FILE2] ...]"
    echo "  FILE: The EFI file to sign (required)"
    echo "  --certificates: Path to PKCS#12 file containing keys and certificates (required)"
    echo "  --nickname: Nickname of the cert/key to use (default to the first key)"
    echo "  --password-file: Path to password file to unlock the CERTS file (optional)"
    exit 1
}

list_nicknames() {
  certutil -L -d /etc/pki/pesign 2>/dev/null \
  | awk 'BEGIN{IGNORECASE=1}
      NF && $0 !~ /^Certificate Nickname/ && $0 !~ /^ *SSL,S\/MIME,JAR\/XPI/ {
        sub(/[[:space:]]{2,}[^[:space:]]+,[^[:space:]]+,[^[:space:]]+$/,"")
        sub(/[[:space:]]+$/,""); print
      }'
}

CERTS=""
NICKNAME=""
PASSWORD_FILE=""
FILES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --certificates)
            CERTS="$2"
            shift 2
            ;;
        --nickname)
            NICKNAME="$2"
            shift 2
            ;;
        --password-file)
            PASSWORD_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            FILES+=("$1")
            shift
            ;;
    esac
done

if (( ${#FILES[@]} == 0 )); then
    echo "Error: No files specified"
    usage
fi

if [[ -z "$CERTS" ]]; then
    echo "Error: --certificates is required"
    usage
else
    if [[ ! -f "$CERTS" ]]; then
        echo "Error: --certificates file '$CERTS not found"
        echo "Did you specify the /work volume?"
        exit 1
    fi
fi

if [[ ! -z "$PASSWORD_FILE" && ! -f "$PASSWORD_FILE" ]]; then
    echo "Error: Password file $PASSWORD_FILE does not exist"
    exit 1
fi

echo Importing DB keys into pesign nss database
import_cmd=(pk12util -i "$CERTS" -d /etc/pki/pesign)
if [[ ! -z "$NICKNAME" ]]; then
    import_cmd+=(-n "$NICKNAME")
fi
if [[ ! -z "$PASSWORD_FILE" ]]; then
    import_cmd+=(-w "$PASSWORD_FILE")
fi
"${import_cmd[@]}" > /dev/null

if [[ -z "$NICKNAME" ]]; then
    NICKNAME=$(list_nicknames | head -n1)
fi

for file in "${FILES[@]}"; do
    echo "Signing $file with cert '$NICKNAME'"
    pesign -v --force -c "$NICKNAME" -s -i $file -o $file.signed
    mv $file.signed $file
done
