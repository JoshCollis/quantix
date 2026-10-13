#!/usr/bin/env bash

set -oue pipefail

# BlueBuild supplies the recipe's image name as a Containerfile build argument.
IMAGE_NAME="${IMAGE_NAME:-quantix}"
IMAGE_FLAVOR=main
if [[ "${IMAGE_NAME}" == quantix-nvidia-open ]]; then
  IMAGE_FLAVOR=nvidia-open
fi

sed -i 's/plasma.svgz/quantix_logo.svgz/g' /usr/share/plasma/look-and-feel/org.kde.breeze.desktop/contents/splash/Splash.qml

cat > /usr/share/quantix-os/image-info.json <<EOF
{
  "image-name": "${IMAGE_NAME}",
  "image-flavor": "${IMAGE_FLAVOR}",
  "image-vendor": "joshcollis",
  "image-ref": "ostree-image-signed:docker://ghcr.io/joshcollis/${IMAGE_NAME}",
  "image-tag": "stable",
  "image-branch": "main",
  "base-image-name": "Bazzite",
  "fedora-version": "44"
}
EOF
