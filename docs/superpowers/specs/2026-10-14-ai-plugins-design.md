# Plugins, and AI-built plugins ("Kindle a Feature") — Design

**Date:** 2026-10-14
**Status:** Approved (design), 2026-10-14. Michael chose the name **Kindle a Feature**, providers **Anthropic first, then OpenAI-compatible**, and a curated **plugin gallery** for sharing. Build in the phase order below.

## The idea

Michael's description, condensed:

1. A user connects their own AI to Varda (an API key, to start with).
2. Under **Plugins**, next to the usual "install a plugin from a folder or zip", there's a "describe a feature" option.
3. The user writes in plain language what they want. Varda turns that into a prompt for their agent, adding everything the agent needs to know about building a Varda plugin.
4. The agent builds the plugin in real time, and it becomes a new feature in Varda.
5. The user can then share it: their agent opens a pull request, so everyone gets the feature.

This has to rest on a plugin system that actually works, and today's doesn't (see below). So the plan has two halves: a real plugin system first, then the AI layer on top.

## Today's plugin system (2026-10-14)

- pluggy, with only two hooks, `onLoad(app)` and `onUnload(app)`. A plugin gets the whole `VardaApplication` and has to reach into internals to add anything. There is no stable API.
- Discovery is the `plugins/user_plugins/` package inside the source tree, plus `varda.plugins` entry points. The packaged app loads none (by design, since the folder is inside the bundle).
- No Plugins menu, and no way to install, enable, disable or remove a plugin from the app.
- The examples in `user_plugins/examples/` predate most of the current code.

## Part 1 — A plugin system that works

### What a plugin is

A folder, or a zip of one:

```text
spectral-ratio-tool/
  plugin.toml        # name, version, author, description, varda API version, entry module
  plugin.py          # implements hooks using only varda.api
  tests/test_plugin.py   # optional; required for gallery submission
  README.md
```

`plugin.toml` declares `api = "1"`. Varda refuses plugins built for an API version it doesn't support, and says why.

### Where plugins live

They're installed into Varda's app-data folder (`<app data>/plugins/<name>/`), next to the PyTorch runtime and the logs. That way they work in the packaged app and survive updates. Plugins from entry points keep working for developers.

### What plugins can add (hooks, API version 1)

- **`registerAnalyses()`** returns `Analysis` subclasses. This is the most valuable hook, and the natural target for AI-built plugins. An analysis already gets everything for free:
  - an entry in the Processing menu, under its category
  - a settings dialog generated from its Parameters
  - background running with progress
  - its result added to the project
  - recorded provenance
  - optionally, a preview widget
- **`registerDataSources()`** adds file formats (`DataSource` subclasses).
- **`registerStretches()`** and **`registerColorMaps()`** add display options.
- **`registerActions()`** adds app_model actions: menu items for anything else.
- `onLoad` and `onUnload` stay, for setup and teardown.

Workspaces and dock panels come later. They're bigger surfaces and harder to keep stable.

### `varda.api`: the only module plugins import

It re-exports a curated, documented surface:
- `Analysis`, `AnalysisContext` and `ProgressCallback`
- the parameter classes
- `VardaRaster`, `ArrayDataSource`, `BandModel` and helpers such as `readCube` and `mapRaster`
- `DataSource`, `StretchAlgorithm` and app_model's `Action`

Anything else counts as internal and may change. The surface is versioned with `api = "1"`, uses `warnDeprecated` (E4) for retirements, and is checked by an import-linter contract that example plugins import only `varda.api`.

### Plugins menu

- **Manage Plugins…** lists installed plugins (name, version, source, enabled, errors) with Enable, Disable, Remove, Reload, Open Folder and View Code.
- **Install from Folder…** and **Install from Zip…** validate `plugin.toml` and copy the plugin into the app-data folder.
- **Kindle a Feature…** (Part 2).
- **Browse Plugin Gallery…** (Part 3).

### Safety and failure

- A plugin that fails to import or to register is disabled, its error is shown in Manage Plugins, and Varda carries on.
- Plugins are ordinary Python running inside Varda, with the same trust as installing any Python package. The install dialog says so plainly and shows the code's location.

### Dependencies

Version 1: plugins may use only what Varda ships (numpy, scipy, scikit-learn, spectral, rasterio, shapely, …). `plugin.toml` may list `requires`; a missing one disables the plugin with a clear message. Installing extra packages into a per-plugin environment, as the PyTorch runtime does, can come later.

### Developer docs

Two documents:
- `docs/plugins/authoring.md`, a short guide with two complete examples: a new analysis and a new file format.
- `docs/plugins/api.md`, generated from `varda.api`'s docstrings.

These are written for humans, and they are also exactly what the AI agent receives (Part 2), so one set of docs serves both.

## Part 2 — Kindle a Feature (AI-built plugins)

### Connecting an AI

Under **Settings → AI Assistant**:
- **Provider:** Anthropic (Claude) first. Then any OpenAI-compatible endpoint, which also covers local models through Ollama or LM Studio.
- **API key:** stored in the OS keychain (`keyring`), never in a settings file or a session.
- **Model choice and a spending cap per kindling:** tokens and cost are estimated before starting and shown afterward.

**API, not MCP, for this feature.** Here Varda is the client: it asks a model to write code. That's what a model API with tool use is for. MCP is the opposite direction: an outside agent (Claude Code, Claude Desktop) using Varda's tools. That's a valuable separate idea, "Varda as an MCP server", so an agent can open images, run analyses and read spectra. It's listed under Later.

### The flow

1. **Describe.** The user writes something like "a band depth at 1.9 µm map, normalized by the continuum between 1.8 and 2.1 µm". Varda may ask the model one or two clarifying questions before building.
2. **Build.** A small agent loop runs inside Varda, using the provider's tool-use API. The model gets the authoring guide, the `varda.api` reference, two or three example plugins, and the current image's metadata (band count, wavelengths and units, size, no-data). It never gets pixel values unless the user opts in. Its tools:
   - `read_docs(topic)` and `list_examples()` / `read_example(name)`
   - `write_file(path, text)` and `read_file(path)`, confined to the new plugin's own folder
   - `run_checks()`. Varda runs the plugin in a separate Python process with a timeout: import, register, run each new analysis on a small synthetic cube and on a downsampled crop of the current image, then run the plugin's own tests. It returns errors, output shapes and timings.
   - `finish(summary)`

   The loop stops when the checks pass, or at the spending cap or turn limit. Progress streams into the dialog ("writing plugin.py… running checks… fixing a shape error…") with the busy V.
3. **Review.** Varda shows:
   - a plain-language summary
   - where the feature appears, e.g. "Processing → Spectral Parameters → Band Depth 1.9 µm"
   - the code, with highlighting
   - the check results
   - advisory warnings from a static scan: network access, subprocesses, file writes outside the plugin, `eval`/`exec`

   The user chooses **Enable**, **Ask for changes** (another round with their feedback) or **Discard**.
4. **Use.** Once enabled, it's an ordinary installed plugin. The analysis is in the Processing menu right away, and its provenance names the plugin and its version.

### Why analyses first

Most "I wish Varda could…" requests from scientists are an analysis: a spectral index, a band depth, a filter, a classifier tweak or a statistic. The `Analysis` contract is small, pure (image in, image out), testable headlessly and safe to run in a subprocess, which makes it the most reliable target for generated code. Later API versions can widen what kindled plugins may touch.

### Privacy and safety

- **What's sent:** the description, the docs and examples, and the image's metadata.
- **What's never sent without opting in:** pixel data, file paths or ROIs.
- **Running code:** generated code always runs in a separate process for checks. It runs inside Varda only after the user clicks Enable, the same trust step as installing any plugin.
- **Dialog wording:** the wording says plainly that the code comes from an AI, and that the user should read the summary and warnings.

## Part 3 — Sharing back

- **Share with the community…** (on any kindled or local plugin) submits it to a curated **plugin gallery repo**, `varda-pro/plugins`, as a pull request. It doesn't go straight into Varda's own codebase. The gallery's CI runs each plugin's checks on sample data, and maintainers review there.
- **Browse Plugin Gallery…** installs reviewed plugins from it.
- Popular, mature gallery plugins can graduate into Varda itself through a normal PR to the main repo.
- **Making the PR:** Varda signs in to GitHub with the device flow (the user approves a code in the browser, with no tokens pasted). It forks the gallery, commits the plugin folder and the generated README, and opens the pull request with the description, the original request and the check results.

  Alternatively, users of Claude Code or another coding agent can open the PR from the plugin folder themselves. The authoring guide explains how.

## Phases

1. **A working plugin system:** manifest, app-data folder, hooks for API version 1, `varda.api`, the Plugins menu (manage, install from folder or zip), the authoring guide, updated examples, and the packaged app loading user plugins. Tests throughout.
2. **AI connection:** Settings → AI Assistant, keychain storage, a provider interface (Anthropic first, then OpenAI-compatible).
3. **Kindle a Feature:** the agent loop and tools, the subprocess check runner, and the review dialog.
4. **Sharing:** the `varda-pro/plugins` gallery repo with CI, the device-flow PR from Varda, and gallery browsing.
5. **Later:** Varda as an MCP server; plugins with their own dependencies; plugins that add workspaces and panels.

## Decisions (made 2026-10-14)

1. **The name of the AI feature.** Chosen: **"Kindle a Feature…"**. In Tolkien, Varda is Elentári, the Star-kindler, who kindled the stars. Users would be *kindling* features, which ties the app's name to the feature. Alternatives: "Spellcast…", "Incantation…", "Sing a Feature…" (after the Music of the Ainur), or the plain "Describe a Feature…".
2. **Providers for the first version.** Chosen: Anthropic first, then OpenAI-compatible endpoints (which cover OpenAI, local models and many hosted ones).
3. **Where shared plugins go.** Chosen: a curated `varda-pro/plugins` gallery that features can graduate from, not PRs straight into the main Varda repo.
