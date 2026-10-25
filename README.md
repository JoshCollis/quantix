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

### Desktop preferences

`recipes/desktop.yml` is the source of truth for Dracula, Kvantum, Papirus, window buttons, keyboard shortcuts, GTK/GNOME preferences and the bottom panel. The local `desktop-defaults` module compiles these into system defaults and applies a versioned, one-time user migration. It uses KDE's configuration tools and Plasma panel scripting rather than copying a saved desktop with machine-specific activity, screen and widget IDs.

Existing users migrate on their next graphical login; fresh users receive the same setup. There are no automatic backups, and subsequent personal changes are not reset at login. Increment `revision` only when deliberately rolling out another migration. Mouse back/forward buttons retain their normal behavior. Dracula assets still need real files; preferences no longer live in those file overrides. The login screen uses Bazzite's current Plasma Login Manager with the Dracula palette and wallpaper, not the obsolete SDDM overrides.

Brave is installed from its official stable RPM repository and becomes the default browser during migration. Zen is no longer installed by the image; existing browser profile data is not deleted.

### Discord and Vencord

Every build downloads Discord's current official stable Linux release. Discord runs through a writable overlay at `/opt/discord`. The patch layer survives reboots and OS updates that include the identical Discord build. When the bundled Discord build changes, the old patch layer is discarded before mounting the new one; your user settings are not removed.

Discord's newer Linux updater can also install a newer host under your own Discord configuration directory between OS builds. The launcher prefers that host when it is at least as new as the bundled one. Close Discord, then run `vencord-patcher` as your normal user: it patches exactly the host the launcher uses (the system overlay or your writable self-updated host), never immutable `/usr`. Vencord may need reapplying after a Discord update. If the overlay fails, the launcher falls back to unpatched Discord.

### Chunked update trial

The `candidate/desktop-refresh` branch uses `rpm-ostree compose build-chunked-oci`, not the old experimental `rechunk` pipeline. BlueBuild publishes branch/commit tags; it does not change `latest`. Production chunking stays disabled until fresh installation and successive real OS upgrades have passed in a disposable VM on Gill.

Package retention intentionally preserves untagged manifests and signature attachments: these may still be referenced by retained image indexes. Age alone is not sufficient evidence that they are unused.

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
