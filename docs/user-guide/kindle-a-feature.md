# Kindle a Feature

Describe a feature in plain language, and your own AI builds it as a Varda
plugin: a new item in the Processing menu. Varda checks the plugin on your
data before you decide to use it.

(In Tolkien, Varda is the Star-kindler. Here you kindle features.)

## Connect your AI

Kindle a Feature uses your own Anthropic account, so you need an API key.

1. Create a key at [console.anthropic.com](https://console.anthropic.com/settings/keys).
2. In Varda, open **Plugins → AI Assistant Settings…**, paste the key, and
   click **Test Connection**. If Anthropic says the key isn't tied to a
   workspace, also enter your **Workspace ID** (console.anthropic.com →
   Settings → Workspaces), or create the key inside a workspace.
3. Choose a **model**. The most capable model builds the most reliable
   plugins; the cheaper ones suit simple features.
4. Set the **limit per feature**: Varda stops building when a feature has
   used this many tokens, and shows how many each feature used. Anthropic
   bills your account for the tokens used.

The key is stored in your system's keychain (Keychain on macOS, Credential
Manager on Windows, the Secret Service on Linux), never in a file or a
session. **Remove Key** deletes it.

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
again until everything passes. **Stop** ends it after the current step.

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

- **Sent to Anthropic:** your description, Varda's plugin documentation, and
  the image's size, wavelengths and no-data value.
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
