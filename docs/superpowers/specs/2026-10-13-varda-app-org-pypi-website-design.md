# varda-app: GitHub Organization, PyPI Release and Website — Design

**Date:** 2026-10-13
**Status:** Approved (design). Michael chose the names and roles below; work through the phases in order.
**Owner:** Michael Phillips (GitHub `Michael-S-Phillips`)

## Goal

Give Varda one public identity under one name, **varda-app**, in three places:

| Where | Address |
|---|---|
| GitHub organization | `github.com/varda-app` (repo: `github.com/varda-app/Varda`) |
| PyPI | `pip install varda-app` / `uv tool install varda-app`, launched with `varda` |
| Website | `https://varda-app.github.io` |

The import package stays `varda`, and the command stays `varda`. Only the distribution name changes.

## Decisions already made

- **Organization name:** `varda-app`, on GitHub's free plan.
- **People:**

  | GitHub user | Person | Org role |
  |---|---|---|
  | `Michael-S-Phillips` | Michael Phillips | Owner (creates the org) |
  | `Jaysterr` | Jesse Oved | Owner |
  | `emmae04` | Emma Elliott | Member, with write access to Varda |
  | `Hamad-Ayaz` | Hamad Ayaz | Member, with write access to Varda |

- **HyPyRameter stays where it is** (`Michael-S-Phillips/HyPyRameter`). Don't move it, and don't touch its PyPI setup.
- **PyPI distribution name:** `varda-app`.
- **Website:** the organization's own site repo, `varda-app/varda-app.github.io`, built with the brand kit in `resources/brand/` (read `resources/brand/README.md` first).

## Ground rules

- Several steps can only be done by Michael in a browser. They are marked **[Michael]**. When you reach one, stop and ask him to do it, say exactly what to click, then verify it worked before continuing.
- Never create a new repository called `Varda` under `Michael-S-Phillips`. That permanently deletes the redirects from the old address.
- Nothing is published to PyPI until Phase 3's blockers are cleared. A PyPI name can't really be taken back.
- Work on a branch and open pull requests for the code changes. Commit or push only with Michael's go-ahead, per CLAUDE.md.

## Phase 1 — Create the organization and add people

1. **[Michael]** Create the organization at <https://github.com/account/organizations/new>: Free plan, name `varda-app`, owned by his personal account. (GitHub has no API to create organizations on github.com.) Verify with `gh api orgs/varda-app`.
2. Set the profile:
   ```bash
   gh api -X PATCH orgs/varda-app \
     -f name="Varda" \
     -f description="Visualization and analysis of raster data: hyperspectral and multispectral imagery" \
     -f blog="https://varda-app.github.io" \
     -f location="Tucson, Arizona"
   ```
3. Invite the people. If a user isn't a member yet, `PUT .../memberships` sends an invitation:
   ```bash
   gh api -X PUT orgs/varda-app/memberships/Jaysterr  -f role=admin
   gh api -X PUT orgs/varda-app/memberships/emmae04    -f role=member
   gh api -X PUT orgs/varda-app/memberships/Hamad-Ayaz -f role=member
   ```
   Tell Michael that each person has to accept their invitation by email or on GitHub.
4. Create a `core` team with Emma and Hamad (owners don't need it), so members get write access through the team, not one by one. You'll grant the team access to the repo in Phase 2, after the transfer.
5. **Avatar.** GitHub has no API for organization avatars. Render a 512×512 PNG from `resources/brand/icon/varda-icon.svg` using the same Qt rendering as `scripts/generate_icons.py`, and save it as `docs/assets/varda-avatar.png`. **[Michael]** uploads it in the organization's Settings → Profile.
6. Make the organization's profile page: create the repo `varda-app/.github` with `profile/README.md`. Include the wordmark (from `docs/assets/`, served from the Varda repo once it's transferred), one paragraph about Varda, and links to the Varda repo, the website, Releases and PyPI.

## Phase 2 — Transfer the repository

1. Check first:
   - The working tree is clean.
   - No open pull requests are mid-merge (list them for Michael).
   - Search for hard-coded owner references: `grep -rn "Michael-S-Phillips" --include="*.md" --include="*.py" --include="*.toml" --include="*.yml" --include="*.spec" .`. Known ones: `README.md` (the Releases link and the HyPyRameter link; the HyPyRameter link stays as is).
2. Transfer:
   ```bash
   gh api -X POST repos/Michael-S-Phillips/Varda/transfer -f new_owner=varda-app
   ```
   Issues, pull requests, stars, the wiki, releases and history move with the repo. Old web links and git remotes redirect.
3. Update the local clone with `git remote set-url origin git@github.com:varda-app/Varda.git`, then verify with `git fetch`.
4. Give the `core` team write access: `gh api -X PUT orgs/varda-app/teams/core/repos/varda-app/Varda -f permission=push`.
5. On a branch, update references to the new address:
   - the Releases link in `README.md`
   - `[project.urls]` in `pyproject.toml` (Homepage = the website; Source, Issues, Releases = `github.com/varda-app/Varda/...`)
   - the brand docs (`resources/brand/README.md`, `docs/superpowers/specs/2026-10-12-varda-brand-identity-design.md`) where they name the old owner
6. Check that both workflows (`PR_Checks.yml`, `build.yml`) still run in the new location. Actions secrets and settings move with the repo, but confirm the first run.
7. **[Michael]** uploads `docs/assets/varda-social-preview.png` under the repo's Settings → General → Social preview.

## Phase 3 — Publish to PyPI as `varda-app`

### Blockers — clear these before anything is published

A codebase review on 2026-10-13 found these.

1. **No license.** The repo has no LICENSE file, and `pyproject.toml` has no `license` field. That makes Varda legally unusable by anyone else, and PyPI users would see no license.
   - **[Michael] decides the license.** Don't choose one.
   - Things he may want to weigh, as information rather than legal advice:
     - The bundled app includes PyQt6, which is GPL v3 unless you have a commercial license.
     - WISER, the closest comparable tool, is GPL v3.
     - Permissive licenses (BSD-3-Clause, MIT) allow the broadest reuse.
     - Software written at the University of Arizona may need Tech Launch Arizona's sign-off before an open-source release.
   - Once he decides, add `LICENSE` and the SPDX `license` field.
2. **Bundled data is outside the package.**
   - `resources/` and `librarySpectra/` sit at the repo root, and `utilities/resources.py:resource_path` assumes the repo layout (`parents[3]`). A wheel installed from PyPI would likely not find the logo, the brand assets, `resources/spectral_libraries/crism_mica_numerators.csv` or the USGS library.
   - Move what the app needs at runtime inside `src/varda/` (for example `src/varda/_data/`), load it with `importlib.resources`, and keep PyInstaller working by updating `Varda.spec` `datas` and the `_MEIPASS` branch.
   - Test both: a fresh `pip install` of the built wheel in a clean venv, and `uv run pyinstaller Varda.spec`.
3. **Package size.** `librarySpectra/` is about 96 MB in 738 files.
   - Build the wheel and measure it. PyPI's default per-file limit is 100 MB.
   - If the wheel is over about 50 MB, present Michael with options before publishing:
     - compress the library inside the wheel
     - download the USGS library on first use, with a checksum
     - publish it as a separate data package
4. **A version lookup that the rename breaks.** `optional_features/torch_runtime.py:139` calls `metadata.version("varda")`, which fails once the distribution is called `varda-app`. Read the version from one place.
5. **The version is written in two places:** `pyproject.toml` (0.3.1) and the Windows app ID in `main.py:30` (`"varda.0.3.1"`).
   - Take the version from git tags with `setuptools-scm`, since the build backend is already setuptools.
   - Expose it as `varda.__version__` and build the app ID from it.
   - Make sure release tags (`v*`) and the version agree.
6. **Rename the distribution:**
   - Set `name = "varda-app"` in `pyproject.toml`, keeping the `varda` import package and the `varda` script entry point.
   - Update `pip install "varda[...]"` in the README and in comments in `pyproject.toml` to `varda-app[...]`.
   - Add an "Install with pip" section to the README.

### Publish workflow

- Add a publish job that runs on `v*` tags, alongside the existing release build in `build.yml`, or as `publish.yml`. It should:
  1. build the sdist and wheel with `uv build`
  2. install the wheel in a clean environment and run a headless smoke test: import `varda`, load the bundled resources, and run `QT_QPA_PLATFORM=offscreen`, constructing the app without showing the window if that's practical
  3. publish with `pypa/gh-action-pypi-publish` using trusted publishing: `permissions: id-token: write`, in a GitHub environment named `pypi`
- **[Michael]** Because the project doesn't exist on PyPI yet, he registers a **pending publisher** at <https://pypi.org/manage/account/publishing/> with:
  - PyPI project name: `varda-app`
  - Owner: `varda-app`
  - Repository: `Varda`
  - Workflow file: the file name you used
  - Environment: `pypi`

  This has to happen **after** the transfer, because the publisher is tied to the owner name.
- Do a dry run on TestPyPI first, with a separate pending publisher and environment. Then tag the next version and publish for real.
- Afterward: `pip install varda-app` and `uv tool install varda-app` both work in clean environments on macOS, and `varda` launches.

## Phase 4 — Website at varda-app.github.io

Create the repo `varda-app/varda-app.github.io`. Keep it a plain static site: hand-written HTML and CSS, no framework, published with GitHub Pages through a small Actions workflow. Read `resources/brand/README.md` and follow its rules for color, type, clear space and minimum sizes.

**Page content (one page to start):**

1. **Header.** The animated hero lockup (`docs/assets/varda-hero-on-dark.svg` and `-on-light.svg`, switched by `prefers-color-scheme`, holding still under `prefers-reduced-motion`), plus the tagline "visualization and analysis of raster data".
2. **What Varda is:** two or three sentences from the README.
3. **Get Varda:**
   - download buttons for macOS, Windows and Linux, linking to `github.com/varda-app/Varda/releases/latest`, plus the macOS first-launch note from the README
   - `pip install varda-app` and `uv tool install varda-app`, each with a copy button
4. **Features:** short cards for:
   - the Spectral Hourglass workflow
   - ROIs that work across images and coordinate systems
   - PCA, MNF and ICA transforms
   - classifiers
   - HyPyRameter band parameters
   - sessions with autosave

   **[Michael]** provides three or four screenshots. Until then, leave clearly marked placeholders; don't fake them.
5. **Cite Varda:** placeholder text until a Zenodo DOI exists. Add `CITATION.cff` to the Varda repo when the license lands.
6. **People and credit:**
   - the four contributors
   - "Developed at the Space Imagery Center, Lunar and Planetary Laboratory, University of Arizona" as plain text
   - Don't use University of Arizona logos or marks, which need the university's permission on a non-arizona.edu site.
7. **Footer:** GitHub, Releases, PyPI, license (once chosen) and contact.

**Assets and details:**

- Copy the needed brand files into the site repo instead of hot-linking.
- Self-host Poiret One from `resources/brand/fonts/` with its `OFL.txt`.
- Build the favicon from the icon. Add Open Graph and Twitter meta tags using `varda-social-preview.png`.
- Write semantic HTML with good contrast. Make sure the page looks right at 375 px wide and works without JavaScript; the only optional script is copy-to-clipboard.

**Deploy:**

- Enable Pages with `gh api -X POST repos/varda-app/varda-app.github.io/pages -f build_type=workflow` and add the standard Pages workflow.
- Verify that `https://varda-app.github.io` loads, then link it from the Varda README and the organization profile.

## Acceptance checks

- `github.com/varda-app` shows the profile, the avatar, the pinned Varda repo, and the README profile page. Jesse is an owner, and Emma and Hamad are members with write access through `core`.
- `github.com/Michael-S-Phillips/Varda` redirects to `github.com/varda-app/Varda`, and both workflows pass there.
- PyPI shows `varda-app` with a license, project links and a README that renders. `pip install varda-app` then `varda` works in a clean environment.
- `https://varda-app.github.io` loads with the animated header, working download and install sections, and correct social previews.
- `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run ty check` show no new failures.

## Not in scope

- Moving HyPyRameter.
- Buying a custom domain. If Michael buys one later, point it at the organization site and nothing else changes.
- The codebase improvements listed in `docs/superpowers/specs/2026-10-13-lessons-from-napari-astropy-spy-wiser.md`, except the packaging blockers above, which overlap.
