# Quantix &nbsp; [![build-quantix](https://github.com/JoshCollis/quantix/actions/workflows/build.yml/badge.svg)](https://github.com/JoshCollis/quantix/actions/workflows/build.yml)

## Installation

To rebase an existing atomic Fedora installation to the latest build:

- First rebase to the unsigned image, to get the proper signing keys and policies installed:
  ```
  rpm-ostree rebase ostree-unverified-registry:ghcr.io/joshcollis/quantix:latest
  ```
- Reboot to complete the rebase:
  ```
  systemctl reboot
  ```
- Then rebase to the signed image, like so:
  ```
  rpm-ostree rebase ostree-image-signed:docker://ghcr.io/joshcollis/quantix:latest
  ```
- Reboot again to complete the installation
  ```
  systemctl reboot
  ```

The `latest` tag automatically points to the latest Quantix build. Both variants track their upstream Bazzite `stable` image, including its Fedora version.

### NVIDIA Open

For NVIDIA Turing and newer GPUs (including GTX 16-series and RTX 20-series or newer), use `ghcr.io/joshcollis/quantix-nvidia-open:latest` instead of `ghcr.io/joshcollis/quantix:latest` in both rebase commands above. This variant inherits its drivers from `ghcr.io/ublue-os/bazzite-nvidia-open:stable`; older GPUs requiring proprietary kernel modules are not supported by this variant.

CI builds and signs both images independently. Their shared packages, configuration, and theming are defined in `recipes/common.yml`.

The shared VFIO configuration includes the passthrough modules but does not bind any GPU to them; host graphics still uses the upstream drivers unless you explicitly configure device passthrough. Existing user settings in `/etc` or your home directory can override the image defaults.

When rebasing an older AMD/Intel installation to NVIDIA, existing kernel arguments may need updating. If the NVIDIA driver does not load, follow [BlueBuild's NVIDIA rebase guidance](https://blue-build.org/reference/modules/akmods/#nvidia-module-not-loaded-after-rebasing-to-a-new-image).

## ISO

If build on Fedora Atomic, you can generate an offline ISO with the instructions available [here](https://blue-build.org/learn/universal-blue/#fresh-install-from-an-iso). These ISOs cannot unfortunately be distributed on GitHub for free due to large sizes, so for public projects something else has to be used for hosting.

## Verification

### Local checks

With Python 3, PyYAML, Node.js, and [actionlint](https://github.com/rhysd/actionlint) installed:

```bash
python3 -m unittest discover -s tests -v
actionlint
```

These checks cover image variants, metadata, boot configuration, download retries, and package retention. They do not replace full image builds or GPU boot testing.

### Image signatures

These images are signed with [Sigstore](https://www.sigstore.dev/)'s [cosign](https://github.com/sigstore/cosign). You can verify the signature by downloading the `cosign.pub` file from this repo and running the following command:

```bash
cosign verify --key cosign.pub ghcr.io/joshcollis/quantix
```
