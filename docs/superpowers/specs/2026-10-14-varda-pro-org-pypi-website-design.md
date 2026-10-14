# varda-pro: GitHub Organization, PyPI Release and Website — Design

**Date:** 2026-10-14 (first written 2026-10-13 for the name `varda-app`, which belongs to an unrelated GitHub account)
**Status:** Approved (design). Michael chose the name `varda-pro` on 2026-10-14; the people and roles below are unchanged. Work through the phases in order.
**Owner:** Michael Phillips (GitHub `Michael-S-Phillips`)

## Goal

Give Varda one public identity under one name, **varda-pro**, in three places:

| Where | Address |
|---|---|
| GitHub organization | `github.com/varda-pro` (repo: `github.com/varda-pro/Varda`) |
| PyPI | `pip install varda-pro` / `uv tool install varda-pro`, launched with `varda` |
| Website | `https://varda-pro.github.io` |

The import package stays `varda`, and the command stays `varda`. Only the distribution name changes.

## Decisions already made

- **Organization name:** `varda-pro`, on GitHub's free plan. Checked free on 2026-10-14 on GitHub, on PyPI and as `varda-pro.github.io`.
- **Why not narrower names:** Varda should read as a general raster and image-analysis tool, not only a spectroscopy one, so names like `varda-spectral` and `varda-hsi` were rejected.
- **People:**

  | GitHub user | Person | Org role |
  |---|---|---|
  | `Michael-S-Phillips` | Michael Phillips | Owner (creates the org) |
  | `Jaysterr` | Jesse Oved | Owner |
  | `emmae04` | Emma Elliott | Member, with write access to Varda |
  | `Hamad-Ayaz` | Hamad Ayaz | Member, with write access to Varda |

- **HyPyRameter stays where it is** (`Michael-S-Phillips/HyPyRameter`). Don't move it, and don't touch its PyPI setup.
- **PyPI distribution name:** `varda-pro`.
- **Website:** the organization's own site repo, `varda-pro/varda-pro.github.io`, built with the brand kit in `resources/brand/` (read `resources/brand/README.md` first).

## Ground rules

- Several steps can only be done by Michael in a browser. They are marked **[Michael]**. When you reach one, stop and ask him to do it, say exactly what to click, then verify it worked before continuing.
- Never create a new repository called `Varda` under `Michael-S-Phillips`. That permanently deletes the redirects from the old address.
- Nothing is published to PyPI until Phase 3's blockers are cleared. A PyPI name can't really be taken back.
- Work on a branch and open pull requests for the code changes. Wait for the four required checks before merging (branch protection doesn't stop an admin's merge).

## Phase 0 — Demo screenshots and video (doesn't wait for the organization)

Real imagery only: CRISM FRT000047A3 (`frt000047a3_07_if166j_mtr3`, Nili Fossae), downloaded from the PDS to `~/Documents/Software/varda-demo-data/` (outside the repo).

- Capture from the running app (offscreen Qt, `widget.grab()`), at 2x for sharpness, and save under `docs/assets/demo/`.
- **Screenshots** (PNG, about 1600 px wide):
  1. the general workspace: true or false color, a few drawn ROIs, and their mean spectra in the plot
  2. a band parameter or band math result overlaid on the scene, with its legend
  3. the Spectral Hourglass: n-D visualizer, endmember spectra and a map
  4. a classification overlay with the class legend
- **Video:** one short (10–20 s) silent loop, such as clicking pixels to plot spectra and adjusting a stretch, as an MP4 for the website. Also make a size-limited GIF or WebP for the README; GitHub READMEs can't embed MP4 from the repo.
- Keep the README's media small (under about 5 MB in total), and reuse the same files on the website.
- Add a short "See it in action" section near the top of the README.

## Phase 1 — Create the organization and add people

1. **[Michael]** Create the organization at <https://github.com/account/organizations/new>: Free plan, name `varda-pro`, owned by his personal account. (GitHub has no API to create organizations on github.com.) Verify with `gh api orgs/varda-pro`.
2. Set the profile:
   ```bash
   gh api -X PATCH orgs/varda-pro \
     -f name="Varda" \
     -f description="Visualization and analysis of raster data: hyperspectral and multispectral imagery" \
     -f blog="https://varda-pro.github.io" \
     -f location="Tucson, Arizona"
   ```
3. Invite the people. If a user isn't a member yet, `PUT .../memberships` sends an invitation:
   ```bash
   gh api -X PUT orgs/varda-pro/memberships/Jaysterr  -f role=admin
   gh api -X PUT orgs/varda-pro/memberships/emmae04    -f role=member
   gh api -X PUT orgs/varda-pro/memberships/Hamad-Ayaz -f role=member
   ```
   Tell Michael that each person has to accept their invitation by email or on GitHub.
4. Create a `core` team with Emma and Hamad (owners don't need it), so members get write access through the team, not one by one. You'll grant the team access to the repo in Phase 2, after the transfer.
5. **Avatar.** GitHub has no API for organization avatars. Render a 512×512 PNG from `resources/brand/icon/varda-icon.svg` using the same Qt rendering as `scripts/generate_icons.py`, and save it as `docs/assets/varda-avatar.png`. **[Michael]** uploads it in the organization's Settings → Profile.
6. Make the organization's profile page: create the repo `varda-pro/.github` with `profile/README.md`. Include the wordmark (from `docs/assets/`, served from the Varda repo once it's transferred), one paragraph about Varda, and links to the Varda repo, the website, Releases and PyPI.

## Phase 2 — Transfer the repository

1. Check first:
   - The working tree is clean.
   - No open pull requests are mid-merge (list them for Michael).
   - Search for hard-coded owner references: `grep -rn "Michael-S-Phillips" --include="*.md" --include="*.py" --include="*.toml" --include="*.yml" --include="*.spec" .`. Known ones: `README.md` (the Releases link and the HyPyRameter link; the HyPyRameter link stays as is).
2. Transfer:
   ```bash
   gh api -X POST repos/Michael-S-Phillips/Varda/transfer -f new_owner=varda-pro
   ```
   Issues, pull requests, stars, the wiki, releases and history move with the repo. Old web links and git remotes redirect.
3. Update the local clone with `git remote set-url origin git@github.com:varda-pro/Varda.git`, then verify with `git fetch`.
4. Give the `core` team write access: `gh api -X PUT orgs/varda-pro/teams/core/repos/varda-pro/Varda -f permission=push`.
5. On a branch, update references to the new address:
   - the Releases link in `README.md`
   - `[project.urls]` in `pyproject.toml` (Homepage = the website; Source, Issues, Releases = `github.com/varda-pro/Varda/...`)
   - the brand docs (`resources/brand/README.md`, `docs/superpowers/specs/2026-10-12-varda-brand-identity-design.md`) where they name the old owner
6. Check that both workflows (`PR_Checks.yml`, `build.yml`) still run in the new location. Actions secrets and settings move with the repo, but confirm the first run.
7. **[Michael]** uploads `docs/assets/varda-social-preview.png` under the repo's Settings → General → Social preview.

## Phase 3 — Publish to PyPI as `varda-pro`

### Blockers — clear these before anything is published

A codebase review on 2026-10-13 found these. Status as of 2026-10-14 is shown on each.

1. **No license.** ✅ **Done (PR #109):** GPL-3.0-or-later, with `LICENSE`, the SPDX field in `pyproject.toml`, `CITATION.cff` and community files. The original finding: the repo had no LICENSE file, and `pyproject.toml` has no `license` field. That makes Varda legally unusable by anyone else, and PyPI users would see no license.
   - **[Michael] decides the license.** Don't choose one.
   - Things he may want to weigh, as information rather than legal advice:
     - The bundled app includes PyQt6, which is GPL v3 unless you have a commercial license.
     - WISER, the closest comparable tool, is GPL v3.
     - Permissive licenses (BSD-3-Clause, MIT) allow the broadest reuse.
     - Software written at the University of Arizona may need Tech Launch Arizona's sign-off before an open-source release.
   - Once he decides, add `LICENSE` and the SPDX `license` field.
2. **Bundled data is outside the package.** ⏳ **Open.** `resources/` (0.9 MB) and `librarySpectra/` (95 MB) are still at the repo root.
   - `resources/` and `librarySpectra/` sit at the repo root, and `utilities/resources.py:resource_path` assumes the repo layout (`parents[3]`). A wheel installed from PyPI would likely not find the logo, the brand assets, `resources/spectral_libraries/crism_mica_numerators.csv` or the USGS library.
   - Move what the app needs at runtime inside `src/varda/` (for example `src/varda/_data/`), load it with `importlib.resources`, and keep PyInstaller working by updating `Varda.spec` `datas` and the `_MEIPASS` branch.
   - Test both: a fresh `pip install` of the built wheel in a clean venv, and `uv run pyinstaller Varda.spec`.
3. **Package size.** ⏳ **Open.** `librarySpectra/` is about 95 MB in 738 files.
   - Build the wheel and measure it. PyPI's default per-file limit is 100 MB.
   - If the wheel is over about 50 MB, present Michael with options before publishing:
     - compress the library inside the wheel
     - download the USGS library on first use, with a checksum
     - publish it as a separate data package
4. **A version lookup that the rename breaks.** ✅ **Mostly done:** every caller now uses `varda.version.vardaVersion()`, which tries a list of distribution names. Change its first entry from `varda-app` to `varda-pro` in the rename. The original finding: `optional_features/torch_runtime.py:139` calls `metadata.version("varda")`, which fails once the distribution is called `varda-pro`. Read the version from one place.
5. **The version is written in two places.** ◐ **Partly done:** the Windows app ID no longer contains the version (PR #127). The version is still kept by hand in `pyproject.toml` and `CITATION.cff`. `setuptools-scm` remains optional. The original finding: `pyproject.toml` (0.3.1) and the Windows app ID in `main.py:30` (`"varda.0.3.1"`).
   - Take the version from git tags with `setuptools-scm`, since the build backend is already setuptools.
   - Expose it as `varda.__version__` and build the app ID from it.
   - Make sure release tags (`v*`) and the version agree.
6. **Rename the distribution.** ⏳ **Open.**
   - Set `name = "varda-pro"` in `pyproject.toml`, keeping the `varda` import package and the `varda` script entry point.
   - Update `pip install "varda[...]"` in the README and in comments in `pyproject.toml` to `varda-pro[...]`.
   - Add an "Install with pip" section to the README.

### Publish workflow

- Add a publish job that runs on `v*` tags, alongside the existing release build in `build.yml`, or as `publish.yml`. It should:
  1. build the sdist and wheel with `uv build`
  2. install the wheel in a clean environment and run a headless smoke test: import `varda`, load the bundled resources, and run `QT_QPA_PLATFORM=offscreen`, constructing the app without showing the window if that's practical
  3. publish with `pypa/gh-action-pypi-publish` using trusted publishing: `permissions: id-token: write`, in a GitHub environment named `pypi`
- **[Michael]** Because the project doesn't exist on PyPI yet, he registers a **pending publisher** at <https://pypi.org/manage/account/publishing/> with:
  - PyPI project name: `varda-pro`
  - Owner: `varda-pro`
  - Repository: `Varda`
  - Workflow file: the file name you used
  - Environment: `pypi`

  This has to happen **after** the transfer, because the publisher is tied to the owner name.
- Do a dry run on TestPyPI first, with a separate pending publisher and environment. Then tag the next version and publish for real.
- Afterward: `pip install varda-pro` and `uv tool install varda-pro` both work in clean environments on macOS, and `varda` launches.

## Phase 4 — Website at varda-pro.github.io

Create the repo `varda-pro/varda-pro.github.io`. Keep it a plain static site: hand-written HTML and CSS, no framework, published with GitHub Pages through a small Actions workflow. Read `resources/brand/README.md` and follow its rules for color, type, clear space and minimum sizes.

**Page content (one page to start):**

1. **Header.** The animated hero lockup (`docs/assets/varda-hero-on-dark.svg` and `-on-light.svg`, switched by `prefers-color-scheme`, holding still under `prefers-reduced-motion`), plus the tagline "visualization and analysis of raster data".
2. **What Varda is:** two or three sentences from the README.
3. **Get Varda:**
   - download buttons for macOS, Windows and Linux, linking to `github.com/varda-pro/Varda/releases/latest`, plus the macOS first-launch note from the README
   - `pip install varda-pro` and `uv tool install varda-pro`, each with a copy button
4. **See it in action:** the demo video from Phase 0 (MP4 with a poster frame; autoplay muted, looping, and paused under `prefers-reduced-motion`).
5. **Features:** short cards, each with a Phase 0 screenshot where one fits:
   - viewing images: true and false color, stretches, linked side-by-side views, overlays
   - spectra and ROIs: pixel and ROI spectra, ROI classes, statistics, calculated columns
   - analyses: band math and HyPyRameter band parameters, continuum removal, PCA, MNF and ICA, classification, target detection
   - the Spectral Hourglass workflow
   - sessions, autosave, duplicated workspaces and recorded provenance

   Describe Varda as a general raster and image-analysis tool, with hyperspectral support as its strength, not as a spectroscopy-only tool.
6. **Documentation:** a link to the user guide (`docs/user-guide/` in the repo). Rendering the guide on the site can come later.
7. **Cite Varda:** APA and BibTeX from `CITATION.cff`, as **Help → Cite Varda** shows them, and the Zenodo DOI once Michael sets it up.
8. **People and credit:**
   - the four contributors
   - "Developed at the Space Imagery Center, Lunar and Planetary Laboratory, University of Arizona" as plain text
   - Don't use University of Arizona logos or marks, which need the university's permission on a non-arizona.edu site.
9. **Footer:** GitHub, Releases, PyPI, the license (GPL-3.0-or-later) and contact.

**Assets and details:**

- Copy the needed brand files into the site repo instead of hot-linking.
- Self-host Poiret One from `resources/brand/fonts/` with its `OFL.txt`.
- Build the favicon from the icon. Add Open Graph and Twitter meta tags using `varda-social-preview.png`.
- Write semantic HTML with good contrast. Make sure the page looks right at 375 px wide and works without JavaScript; the only optional script is copy-to-clipboard.

**Deploy:**

- Enable Pages with `gh api -X POST repos/varda-pro/varda-pro.github.io/pages -f build_type=workflow` and add the standard Pages workflow.
- Verify that `https://varda-pro.github.io` loads, then link it from the Varda README and the organization profile.

## Acceptance checks

- `github.com/varda-pro` shows the profile, the avatar, the pinned Varda repo, and the README profile page. Jesse is an owner, and Emma and Hamad are members with write access through `core`.
- `github.com/Michael-S-Phillips/Varda` redirects to `github.com/varda-pro/Varda`, and both workflows pass there.
- PyPI shows `varda-pro` with a license, project links and a README that renders. `pip install varda-pro` then `varda` works in a clean environment.
- `https://varda-pro.github.io` loads with the animated header, working download and install sections, and correct social previews.
- `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run ty check` show no new failures.

## Not in scope

- Moving HyPyRameter.
- Buying a custom domain. If Michael buys one later, point it at the organization site and nothing else changes.
- The codebase improvements listed in `docs/superpowers/specs/2026-10-13-lessons-from-napari-astropy-spy-wiser.md`, except the packaging blockers above, which overlap.
