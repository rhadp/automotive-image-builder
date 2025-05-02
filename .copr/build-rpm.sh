#!/bin/bash
set -e

PACKAGE_NAME="automotive-image-builder"
POSITIONAL_ARGS=()
GENERATE_SPEC=false
BUILD_SOURCE=false
BUILD_BINARY=false
DEV_RELEASE=false
PRINT_SOURCE_PATH=false
DEV_RELEASE_SUFFIX=""
SOURCE_FILENAME=""
OUTPUT_DIR=$(pwd)

while [[ $# -gt 0 ]]; do
  case $1 in
    -gs|--generate-spec)
      GENERATE_SPEC=true
      shift
      ;;
    -bs|--build-source)
      BUILD_SOURCE=true
      shift
      ;;
    -bb|--build-binary)
      BUILD_SOURCE=true
      BUILD_BINARY=true
      shift
      ;;
    -psp|--print-source-path)
      PRINT_SOURCE_PATH=true
      shift
      ;;
    -h|--help)
      echo "build-rpm.sh [-bs|-bb] spec_file [output_dir]"
      exit 0
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

# Store SPEC variable from positional arg
if [ ${#POSITIONAL_ARGS[@]} -ge 1 ]
then
  ARG=${POSITIONAL_ARGS[0]}
  if [ -d "$ARG" ]
  then
    SPEC=$(realpath "$ARG"/$PACKAGE_NAME.spec.in)
  elif [ -f "$ARG" ]; then
    SPEC=$(realpath -s "$ARG")
    if [[ "$SPEC" == */.copr/dev.spec ]]
    then
      DEV_RELEASE=true
      COMMITS_NUM_SINCE_LAST_TAG=$(git log $(git describe --tags --abbrev=0)..HEAD --oneline | wc -l)
      COMMIT_HASH=$(git log -1 --pretty=format:%h)
      DEV_RELEASE_SUFFIX=".dev$COMMITS_NUM_SINCE_LAST_TAG+$COMMIT_HASH"
    fi
  else
    fatal "Spec file doesn't exists: $ARG"
  fi
fi

# Store OUTPUT_DIR variable from positional arg
if [ ${#POSITIONAL_ARGS[@]} -ge 2 ]
then
  OUTPUT_DIR=${POSITIONAL_ARGS[1]}
fi

[ "${#POSITIONAL_ARGS[@]}" -gt 0 ] || fatal "missing parameters"

if [ -z "$PACKAGE_VERSION" ] && [ -f ./aib/version.py ]
then
  PACKAGE_VERSION=$(python3 ./aib/version.py)
fi

if [ $GENERATE_SPEC = true ] || [ $BUILD_SOURCE = true ]
then
  rm -rf .rpmbuild
  mkdir -p .rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

  # Copy spec file to the SPECS directory
  cp "$SPEC" .rpmbuild/SPECS/$PACKAGE_NAME.spec

  # Set package version to the spec file
  sed -e "s/@@VERSION@@/$PACKAGE_VERSION/g" -i .rpmbuild/SPECS/$PACKAGE_NAME.spec

  # Add the dev_release_suffix with the commit hash if it is a dev release
  if [ $DEV_RELEASE = true ]
  then
    OLD_SPEC_RELEASE=$(grep "^Release:" .rpmbuild/SPECS/$PACKAGE_NAME.spec)
    NEW_SPEC_RELEASE=${OLD_SPEC_RELEASE/1%/1$DEV_RELEASE_SUFFIX%}
    sed -e "s/^Release:.*$/$NEW_SPEC_RELEASE/g" -i .rpmbuild/SPECS/$PACKAGE_NAME.spec
    sed -e "s/.tar.gz/$DEV_RELEASE_SUFFIX.tar.gz/g" -i .rpmbuild/SPECS/$PACKAGE_NAME.spec
  fi
fi

if [ $BUILD_SOURCE = true ]
then
  make generate-manifest-doc
  SOURCE_FILENAME="$PACKAGE_NAME-$PACKAGE_VERSION$DEV_RELEASE_SUFFIX.tar.gz"
  cp -f .rpmbuild/SPECS/$PACKAGE_NAME.spec .
  git archive \
    -o ".rpmbuild/SOURCES/$SOURCE_FILENAME" \
    --prefix="$PACKAGE_NAME-$PACKAGE_VERSION/docs/" \
    --add-file docs/manifest.html \
    --add-file docs/manifest.md \
    --prefix="$PACKAGE_NAME-$PACKAGE_VERSION/" \
    --add-file $PACKAGE_NAME.spec \
    HEAD
  rm $PACKAGE_NAME.spec
fi

if [ $BUILD_BINARY = true ]
then
  rpmbuild --define "_topdir $(pwd)/.rpmbuild" -ba .rpmbuild/SPECS/$PACKAGE_NAME.spec
elif [ $BUILD_SOURCE = true ] && [ $BUILD_BINARY = false ]; then
  rpmbuild --define "_topdir $(pwd)/.rpmbuild" -bs .rpmbuild/SPECS/$PACKAGE_NAME.spec
fi

#Copy spec file to the output_dir
cp -f .rpmbuild/SPECS/$PACKAGE_NAME.spec "$OUTPUT_DIR"

#Copy rpm packages to the output_dir
find .rpmbuild -name "*.rpm" -exec cp {} "$OUTPUT_DIR" \;

#Copy tar file to the output_dir
find .rpmbuild -name "*.tar.gz" -exec cp {} "$OUTPUT_DIR" \;
if [ $PRINT_SOURCE_PATH = true ]
then
  echo "$OUTPUT_DIR/$SOURCE_FILENAME"
fi

# Clean .rpmbuild directory
rm -fr .rpmbuild
