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

### Verified upstream base (2026-11-04)

The official [Bazzite Stable release 45.20261104](https://github.com/ublue-os/bazzite/releases/tag/45.20261104), published at 00:50:05 UTC on November 4, is Fedora 45. Its [build definitions](https://github.com/ublue-os/bazzite/blob/e1e1f97053a8332cdefae12e5f61d4696b0d940a/build.py) define both `bazzite` and `bazzite-nvidia-open` on Fedora 45. Quantix keeps the supported `stable` channel for each, not a guessed `45` tag. The CPE metadata now reflects Fedora 45; check it again when upstream advances.

Bazzite's [shared initialization](https://github.com/ublue-os/bazzite/blob/e1e1f97053a8332cdefae12e5f61d4696b0d940a/build_files/bazzite/04-initialize.sh) installs `terra-release`, `terra-release-extras` and `terra-release-mesa` for both variants. Quantix inherits their repository definitions, priorities and exclusions without copying, overwriting or re-adding them. In [run 41730786357](https://github.com/JoshCollis/quantix/actions/runs/41730786357), the standard variant resolved Fedora 45 and failed at 2026-11-03T22:29:05 UTC when DNF5 rejected duplicate ID `terra` in `/usr/share/dnf5/repos.d/terra.repo`; the successful NVIDIA job still resolved Fedora 44. That older success does not justify retaining duplicate definitions or adding a variant-specific fallback.

Hermes's live official GHCR verification on 2026-11-04 confirmed that `stable` and `45.20261104` resolve to the same manifest **within each variant**:

| Upstream image | Manifest digest for both tags |
| --- | --- |
| `ghcr.io/ublue-os/bazzite` | `sha256:9ef3035588c6760e96c5064a1920db35c012c6c8e7d20ac6c1c31a04ed682e0b` |
| `ghcr.io/ublue-os/bazzite-nvidia-open` | `sha256:1afdfa96a8011ae269e8a79dc550e1024fb953f19b3a0483c6522ad4d5d1f3d1` |

Both manifests are Linux `amd64`, report image version `45.20261104` and source revision `e1e1f97053a8332cdefae12e5f61d4696b0d940a`, and carry `containers.bootc=1`, `ostree.bootable=true` and `ostree.linux=7.2.15-ogc1.1.fc45.x86_64`. For each manifest, Hermes verified an ECDSA signature from its legacy OCI cosign `.sig` artifact using the [official public key at that pinned upstream revision](https://github.com/ublue-os/bazzite/blob/e1e1f97053a8332cdefae12e5f61d4696b0d940a/cosign.pub), including a matching signed-payload manifest digest.

These digests document the verified upstream snapshot, not recipe pins. Both recipes continue following the officially supported `stable` release stream. Upstream verification is not evidence of a new Quantix publication: acceptance still requires successful builds and publication of **both** Quantix variants.

### Desktop preferences

`recipes/desktop.yml` is the source of truth for Dracula, Kvantum, Papirus, window buttons, keyboard shortcuts, GTK/GNOME preferences and the bottom panel. The local `desktop-defaults` module compiles these into system defaults and applies a versioned, one-time user migration. It uses KDE's configuration tools and Plasma panel scripting rather than copying a saved desktop with machine-specific activity, screen and widget IDs.

Image build-time configuration is written to `/etc`, as required by BlueBuild/bootc. OSTree creates the read-only `/usr/etc` defaults during deployment; writing to `/usr/etc` in the build can lose configuration during chunked image composition.

Existing users migrate on their next graphical login; fresh users receive the same setup. There are no automatic backups, and subsequent personal changes are not reset at login. Increment `revision` only when deliberately rolling out another migration. Mouse back/forward buttons retain their normal behavior. Dracula assets still need real files; preferences no longer live in those file overrides. The login screen uses Bazzite's current Plasma Login Manager with the Dracula palette and wallpaper, not the obsolete SDDM overrides.

Brave is installed from its official stable RPM repository and becomes the default browser during migration. Zen is no longer installed by the image; existing browser profile data is not deleted.

### Discord and Vencord

Every build downloads Discord's current official stable Linux release, including its native modules and updater metadata. The launcher registers that bundled host with the native updater without replacing your settings or newer personal installs. Each user gets their own installer identity. Discord runs through a writable overlay at `/opt/discord`. The patch layer survives reboots and OS updates that include the identical Discord build. When the bundled Discord build changes, the old patch layer is discarded before mounting the new one; your user settings are not removed.

The current upstream updater requires a real executable inside a per-user `app-VERSION` directory. The helper copies only that executable once per bundled version, linking resources and bundled modules to the overlay rather than duplicating the entire installation. Native module updates remain user-writable. Only Quantix-managed host directories are discarded when the bundled host changes; actual self-updated installations are left to Discord's own updater.

Discord's newer Linux updater can also install a newer host under your own Discord configuration directory between OS builds. The launcher prefers that host when it is at least as new as the bundled one. Close Discord, then run `vencord-patcher` as your normal user: it patches exactly the host the launcher uses (the system overlay or your writable self-updated host), never immutable `/usr`. Vencord may need reapplying after a Discord update. If the overlay fails, the launcher falls back to unpatched Discord.

### Chunked updates

Images use `rpm-ostree compose build-chunked-oci`, not the old experimental `rechunk` pipeline. This was validated on Gill with a production-to-candidate migration, successive signed OS upgrades, and a fresh installation before enabling it for production. Existing users can keep their normal update workflow.

Builds always run the runner's unused-software cleanup, but available capacity varies. In [run 41863564291](https://github.com/JoshCollis/quantix/actions/runs/41863564291), the standard image published successfully; NVIDIA completed its unchunked build, pruned unused storage (reclaiming 0 B), then pulled its previous `latest` image as a composition baseline. At 16:12:15 UTC on November 4, writing the new OSTree commit exceeded the 3% free-space reserve. The action's disk report showed a 72 G root filesystem with 53 G available after cleanup, not the 127 GiB available in the earlier successful trial. The failure was during composition, not package installation, and does not justify removing packages or weakening that reserve.

Only NVIDIA now sets `rechunk_clear_plan: true` through the recipe matrix condition. [Action v1.13](https://github.com/blue-build/github-action/blob/v1.13/action.yml) passes this as `BB_BUILD_RECHUNK_CLEAR_PLAN`; the logged CLI, BlueBuild 0.9.40 (`ed31079e`), [forwards it to `BuildChunkedOciOpts.clear_plan`](https://github.com/blue-build/cli/blob/v0.9.40/src/commands/build.rs#L471-L484). Its [chunked-composition implementation](https://github.com/blue-build/cli/blob/v0.9.40/process/drivers/traits.rs#L431-L472) skips the previous-image pull when clear-plan is true; otherwise it retains that baseline until composition finishes. This avoids the extra baseline storage, not the space required for the new rootfs and commit. NVIDIA still uses `rpm-ostree compose build-chunked-oci` and normal image signing, but no longer preserves the previous build's chunk layout, so cross-version chunk reuse may decrease and update downloads may grow. Standard builds retain baseline reuse. This source-validated capacity mitigation still requires a successful NVIDIA CI publication and registry verification; it is not a new image boot test or a claim that the failed NVIDIA build published.

During the October 2026 trial, successive real updates reused 124–125 of 129 chunks and downloaded about 1.1 GB instead of the roughly 6.6 GB full image. Desktop defaults migrated automatically, later user edits were preserved, and an unchanged bundled Discord retained its Vencord patch across upgrades. Fresh-user desktop defaults and the installed Discord/Vencord helpers were also exercised in a separate VM. These figures describe the tested builds, not a guaranteed size for every future update.

Package retention intentionally preserves untagged manifests and signature attachments: these may still be referenced by retained image indexes. Age alone is not sufficient evidence that they are unused.

### Virtualization and legacy passthrough cleanup

Quantix uses the standard upstream Bazzite kernel, drivers and initramfs, retaining upstream KVM/IOMMU/VFIO capabilities without custom passthrough defaults or KVM/scheduler tuning. `virt-manager`, `virt-viewer`, libvirt, QEMU, the virtual display/SPICE/USB helpers, `libvirtd` and the software-TPM labeling workaround remain. Image signing and upstream Secure Boot support are unchanged. No VM disks or definitions are removed.

Updating the image does **not** guarantee removal of persistent kernel arguments or locally modified `/etc` files. Existing per-machine configuration is unknown. There is no automatic installed-system cleanup. After both fixed images have published, an administrator can perform this one-time cleanup on an existing installation during a planned maintenance window:

1. Inspect the booted and pending deployments, persistent arguments and local initramfs state first:

   ```bash
   rpm-ostree status
   rpm-ostree kargs
   cat /proc/cmdline
   rpm-ostree initramfs
   rpm-ostree initramfs-etc
   sudo ls -l /etc/dracut.conf.d/vfio.conf
   sudo cat /etc/dracut.conf.d/vfio.conf
   ```

   A missing file needs no action. The exact legacy Quantix file contains only:

   ```text
   add_drivers+=" vfio vfio_iommu_type1 vfio-pci "
   ```

2. Only if that file is unchanged, is a regular file (not a symlink), and is no longer intentionally needed, back it up outside `dracut.conf.d`, then remove it with `sudo rm -- /etc/dracut.conf.d/vfio.conf`. Do not remove the directory, other dracut/modprobe files, GPU bindings or VM data. If it differs, stop and review the local changes instead. If `rpm-ostree initramfs-etc` lists this exact file as tracked, untrack only it with `sudo rpm-ostree initramfs-etc --untrack=/etc/dracut.conf.d/vfio.conf`; never use `--untrack-all`.

3. After confirming these exact values came from legacy Quantix and are not deliberately retained for this machine, remove only those legacy tokens from the default deployment (omit any option you intend to keep):

   ```bash
   sudo rpm-ostree kargs \
     --delete-if-present=kvm.ignore_msrs=1 \
     --delete-if-present=kvm.report_ignored_msrs=0 \
     --delete-if-present=preempt=voluntary \
     --delete-if-present=gpu_sched.sched_policy=0 \
     --delete-if-present=iommu=pt \
     --delete-if-present=rd.driver.pre=vfio_pci \
     --delete-if-present=vfio_pci.disable_vga=1 \
     --delete-if-present=amd_iommu=on \
     --delete-if-present=intel_iommu=on
   ```

   Do not delete by key prefix or reset the entire command line: preserve storage, encryption, resume, graphics and unrelated personal arguments. Combined values such as `rd.driver.pre=vfio_pci,other_driver` are **not** the legacy token and need individual review.

4. The removed BlueBuild `initramfs` module generated the image's initramfs; it does not prove client-side regeneration was enabled. Only if local regeneration is enabled **solely** for this old Quantix VFIO setup, disable it with `sudo rpm-ostree initramfs --disable` to use the fixed image's upstream initramfs. Otherwise preserve it and review how to regenerate for the machine's remaining configuration; do not run blanket `dracut --force` commands or delete boot artifacts.

5. Use the normal signed image update workflow and inspect `rpm-ostree status` and `rpm-ostree kargs` again before a separately approved reboot. After booting the fixed deployment, recheck `/proc/cmdline`, the file and local initramfs state. Previous rollback deployments remain unchanged. No cleanup commands above are run by the image or these tests.

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

These checks cover the two stable image variants, inherited Terra repo IDs, Fedora 45 metadata, absence of custom passthrough/kernel tuning, preservation of virtualization and signing, download retries, and package retention. They do not replace full image builds, registry/signature verification or GPU boot testing; successful publication of both variants is required for acceptance.

### Image signatures

These images are signed with [Sigstore](https://www.sigstore.dev/)'s [cosign](https://github.com/sigstore/cosign). You can verify the signature by downloading the `cosign.pub` file from this repo and running the following command:

```bash
cosign verify --key cosign.pub ghcr.io/joshcollis/quantix
```
