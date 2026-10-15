# Kindle a Feature

Describe a feature in plain language, and your own AI builds it as a Varda
plugin: a new item in the Processing menu. Varda checks the plugin on your
data before you decide to use it.

(In Tolkien, Varda is the Star-kindler. Here you kindle features.)

## Connect your AI

Kindle a Feature uses an AI you choose. Open **Plugins → AI Assistant
Settings…**, pick a **provider**, fill in its details, and click **Test
Connection**.

- **Anthropic (Claude):** create a key at
  [console.anthropic.com](https://console.anthropic.com/settings/keys) and
  paste it. If Anthropic says the key isn't tied to a workspace, also enter
  your **Workspace ID** (console.anthropic.com → Settings → Workspaces), or
  create the key inside a workspace.
- **OpenAI:** create a key at
  [platform.openai.com](https://platform.openai.com/api-keys), paste it, and
  click **Load Models** to pick a model.
- **OpenAI-compatible server:** any server that speaks OpenAI's Chat
  Completions API, including models running on your own computer:
  - **Ollama**: `ollama serve`, then `ollama pull` a model. The address is
    `http://localhost:11434/v1`.
  - **LM Studio**: start its local server (Developer tab). The address is
    `http://localhost:1234/v1`.
  - Others, such as vLLM, llama.cpp's server or a hosted service: enter
    their `/v1` address.

  **Preset…** fills in the Ollama and LM Studio addresses. Local servers
  don't need a key; leave it empty. **Load Models** lists what the server
  offers (older Ollama versions don't list them: type the name as
  `ollama list` shows it).

Then choose a **model**. The most capable model builds the most reliable
plugins; the cheaper ones suit simple features. A local model must
**support tool calls** (Qwen3, Llama 3.1 or later and Mistral Small do, for
example), and it needs a context window of **32k tokens or more**. Ollama's
default is much smaller: set `OLLAMA_CONTEXT_LENGTH=32768` before
`ollama serve`, or set the context length in LM Studio. Varda stops if the
model doesn't make tool calls. Expect a local model to be slower and less
reliable than the hosted ones.

Set the **limit per feature**: Varda stops building when a feature (or a
round of changes) has used this many tokens, and shows the count as it goes.
With Anthropic, cached text counts a tenth, as it's billed. Hosted providers
bill your account for what's used; a local model costs nothing but time.

Keys are stored in your system's keychain (Keychain on macOS, Credential
Manager on Windows, the Secret Service on Linux), one per provider, never in
a file or a session. **Remove Key** deletes the chosen provider's key.

## Kindle a feature

1. Open **Plugins → Kindle a Feature…**.
2. Describe what Varda should do, for example:
   > A band depth map at 1.9 µm, against a straight-line continuum between
   > 1.8 and 2.1 µm.

   Name the wavelengths, the formula or the method if you know them. Anything
   left open becomes a setting you can change when you run it.
3. Choose the image to build it for, and click **Kindle**.

Varda shows the AI's progress as it reads the plugin documentation, writes
the plugin and its tests, and runs the checks. It fixes what fails and checks
again until everything passes. **Stop** ends it after the current step. If it
stops before finishing (at the token limit, say), write "continue" and click
**Ask for Changes** to pick up where it left off.

## Review it

When it's done, Varda shows:

- a **summary** of what the feature does and how to read its result
- where it **appears**, e.g. Processing → Spectral Parameters → Band Depth 1.9 µm
- **warnings**, if the code does anything you should know about: network
  access, starting other programs, writing files, or running text as code
- the **checks**: the feature run on a synthetic image and on a crop of your
  image, and the plugin's own tests
- the **code**, file by file, and the build log

Then choose:

- **Enable** installs the plugin. Its analysis is in the Processing menu right
  away, and each result records the plugin and its version.
- **Ask for Changes** sends your feedback for another round, e.g. "also
  output the band center".
- **Discard** throws it away.

Enabled plugins are listed in **Plugins → Manage Plugins…**, where you can
disable, reload or remove them like any other plugin.

## Privacy and safety

- **Sent to your AI provider** (or your own server, for a local model): your
  description, Varda's plugin documentation, and the image's size,
  wavelengths and no-data value.
- **Never sent:** the image's pixels, file paths or ROIs. The checks that run
  the plugin on a crop of your image happen on your computer.
- **Running the code:** while it's being built, the plugin only runs in a
  separate Varda process with a time limit, so a broken plugin can't crash
  Varda. It runs inside Varda only after you click Enable, the same trust step
  as installing any plugin. The code comes from an AI: read the summary and
  the warnings first.

## Sharing

A kindled plugin is an ordinary plugin folder in Varda's plugins folder
(**Manage Plugins → Open Folder**). Zip it to share it; others install it with
**Plugins → Install from Zip…**. A curated plugin gallery is coming. To write
or change plugins by hand, see the [plugin authoring guide](../plugins/authoring.md).
