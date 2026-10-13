# Varda brand

The approved Varda identity: the app icon, wordmark, lockup, splash, busy indicator and
typeface. The implementation plan for the app and the GitHub page is in
`docs/superpowers/specs/2026-10-12-varda-brand-identity-design.md`.

**The idea.** The V is a reflectance spectrum with an absorption band. The dotted line is
the continuum. Above the halfway cut, each letter is part of one continuous spectrum that
runs from violet to near-infrared. Below the cut, the letters are plain white on dark
grounds and ink on light grounds. The r flows into the d. The d leaves its stem through a
second absorption band, which then rises into the last a.

These files are generated from the design source, so don't edit them by hand. To make a
change, ask for a new export.

## Files

"on-dark" means the file is made for dark backgrounds, and "on-light" for light ones.

| File | Use |
|---|---|
| `icon/varda-icon.svg` | App icon on an ink tile, full-bleed 512. It is the source for `resources/logo.svg`, the window icon and the Windows `.ico` |
| `icon/varda-icon-macos.svg` | The same icon on Apple's 1024 grid (an 824 tile with 100 px margins and a soft shadow). It is the source for `.icns` |
| `icon/varda-icon-paper.svg` | Alternate icon on a light tile. Not used by default |
| `icon/varda-mark-on-dark.svg`, `-on-light.svg` | The V mark with no tile, for an About box or an empty state |
| `wordmark/varda-wordmark-on-dark.svg`, `-on-light.svg` | Primary wordmark, with the dotted continuum |
| `wordmark/varda-wordmark-small-on-dark.svg`, `-on-light.svg` | The same wordmark without the dots, for 30–60 px tall |
| `wordmark/varda-wordmark-mono-white.svg`, `-mono-ink.svg` | One-color versions, for single-color printing, embossing and overlays on photos |
| `lockup/varda-lockup-on-dark.svg`, `-on-light.svg` | Wordmark over the tagline "visualization and analysis of raster data". The tagline is set exactly to the wordmark's width |
| `splash/varda-splash.svg` | Static splash: a 16:9 ink panel (logical 640×360) with the lockup centered. It is also the last frame of the animation |
| `splash/splash-motion.json` | The "one pen, branching" draw-on for QPainter (schema 2): strokes with keyframed progress, gradient, dots and tagline timing. See `docs/superpowers/specs/2026-10-13-splash-motion-v2-design.md` |
| `splash/varda-splash-tagline.svg` | The tagline on its own, in splash coordinates, which the animation fades in |
| `loader/loader-motion.json` | Busy-indicator ("redraw") animation data for QPainter |
| `loader/varda-loader-web-on-dark.svg`, `-on-light.svg` | The busy indicator as a CSS-animated SVG, for web pages only |
| `fonts/PoiretOne-Regular.ttf`, `fonts/OFL.txt` | Poiret One, under the SIL Open Font License. Ship the OFL file with the font |

GitHub-only assets are in `docs/assets/`:

- `varda-hero-on-dark.svg` and `varda-hero-on-light.svg` are the README header. They draw the
  logo on once with the "one pen, branching" motion (about 3.9 s) and then hold. With reduced
  motion they show the final frame.
- `varda-social-preview.png` (1280×640) is the image for the repository's social preview.

### Qt compatibility

Qt's SVG renderer ignores `clipPath`, masks, filters, CSS and animation. Every static SVG
above avoids all of these: the white lower halves are real geometry, not a clipped copy of
the letters. Each one was checked with `QSvgRenderer` (PyQt6 6.10) against Chromium.

The animated SVGs (`docs/assets/varda-hero-*`, `loader/varda-loader-web-*`) are for
browsers only. In the app, paint the motion from the JSON files instead.

## Color

| Token | Hex | Use |
|---|---|---|
| Ink | `#110D2B` | Dark ground, icon tile, ink lettering on light grounds |
| Panel | `#1C1938` | Raised dark surface |
| Paper | `#F6F4EF` | Light ground, white lettering on dark grounds |
| Tagline on dark | `#D6D2EE` | Tagline and secondary text on Ink |

The spectral ramp runs violet to near-infrared, left to right, as a horizontal linear
gradient across the full width of the mark:

`#7A5CFF` `#4479FF` `#18B4E0` `#2DC285` `#F0BE2C` `#FF8838` `#EE4258` `#B4235F`
(eight evenly spaced stops)

## Type

**Poiret One** is the display typeface. Use it for the tagline, the splash and large
headings. Don't use it for UI body text, tables or numbers, because it is too light and
too stylized at text sizes. The tagline uses tracking of about 0.08 em and is justified to
the wordmark's width.

## Rules

- **Clear space.** Keep at least half the x-height clear on every side. That is the
  distance from the baseline to the cut, about 30% of the wordmark's height.
- **Minimum size.** Use the wordmark with dots at 60 px tall or more. Use the small
  version (no dots) from 30 to 60 px. Below 30 px, use the app icon.
- **Grounds.** Use the "on-dark" files on Ink or darker and the "on-light" files on Paper
  or white. On photos or busy images, use a mono file.
- **Don't** recolor the spectrum, reverse its direction, or stretch, rotate, outline or
  add effects to the mark.
- **Don't** set the word "Varda" in a font in place of the wordmark.
