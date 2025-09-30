#!/usr/bin/env bash
set -euo pipefail

PASSWORD_FILE=""

usage() {
    echo "Usage: $0 [--password-file PASSWORD_FILE] [--nickname NICK] [OUTDIR]"
    echo "  OUTDIR: Directory where keys are generated"
    echo "  --password-file: Path to password file for generated PKCS#12 file"
    echo "  --nickname: Nickname for the cert (default is test-key)"
    exit 1
}

NICKNAME="test-key"
PASSWORD_FILE=""
OUTDIR=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --password-file)
            PASSWORD_FILE=$(realpath "$2")
            shift 2
            ;;
        --nickname)
            NICKNAME="$2"
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
            if [[ -z "$OUTDIR" ]]; then
                OUTDIR+="$1"
            else
                echo "To many argument"
                usage
            fi
            shift
            ;;
    esac
done

if [[ -z "$OUTDIR" ]]; then
    echo "Error: No out dir specified"
    usage
fi

mkdir -p "$OUTDIR"
cd "$OUTDIR"

echo "Generating secureboot keys in $OUTDIR"
# Key sizes: 3072 for PK/KEK, 2048/3072 for db both fine.
openssl genrsa -out PK.key 3072
openssl req -new -x509 -sha256 -subj "/CN=VM Platform Key/" -key PK.key -out PK.crt -days 3650
openssl x509 -in PK.crt -outform DER -out PK.cer

openssl genrsa -out KEK.key 3072
openssl req -new -x509 -sha256 -subj "/CN=VM Key-Exchange Key/" -key KEK.key -out KEK.crt -days 3650
openssl x509 -in KEK.crt -outform DER -out KEK.cer

openssl genrsa -out db.key 3072
openssl req -new -x509 -sha256 -subj "/CN=VM db (Allowed Signer)/" -key db.key -out db.crt -days 3650
openssl x509 -in db.crt -outform DER -out db.cer

# create ESL and AUTH blobs - Requires a GUID; any stable value is fine for testing.
GUID="$(uuid -v4 || uuidgen)"
echo "$GUID" > GUID.txt

cert-to-efi-sig-list -g "$GUID" PK.crt  PK.esl
cert-to-efi-sig-list -g "$GUID" KEK.crt KEK.esl
cert-to-efi-sig-list -g "$GUID" db.crt  db.esl

# Create signed updates (AUTH) for use when Secure Boot is already enforcing.
sign-efi-sig-list -k PK.key -c PK.crt PK  PK.esl  PK.auth > /dev/null
sign-efi-sig-list -k PK.key -c PK.crt KEK KEK.esl KEK.auth > /dev/null
sign-efi-sig-list -k KEK.key -c KEK.crt db  db.esl  db.auth > /dev/null

# Create an (encrypted) PKCS#12 file with the DB cert and key, with name "test-key"
echo "Exporting (encrypted) PKCS#12 file with cert nickname $NICKNAME"
if [[ -z "$PASSWORD_FILE" ]]; then
    openssl pkcs12 -export -inkey db.key -in db.crt -out db.p12 -name $NICKNAME
else
    openssl pkcs12 -passout file:"$PASSWORD_FILE" -export -inkey db.key -in db.crt -out db.p12 -name $NICKNAME
fi

echo "Keys generated under $OUTDIR"
