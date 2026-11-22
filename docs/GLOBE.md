# Earth globe (hero HUD)

Interactive 3D Earth in the top-right of the hero on `collection`, `logos`, `certificates`,
`presentations`, `skills`, `music` and the hub (`index`). It replaces the old clock/XY readout.
`projects.html` and the project sub-sites do not load `fx.js`, so they never create or load it.

| File | Role |
| --- | --- |
| `js/fx.js` (`hero()`) | creates `.fx-hud`; lazy-loads the three scripts when it nears the viewport |
| `js/globe-data.js` | offline time-zone → city table, NOAA sunrise/sunset |
| `js/globe.js` | DOM mount, `Info` model (panel HTML, precise-location request) |
| `js/globe-scene.js` | three.js scene, render loop, hover/drag/tap |
| `css/fx.css` (end) | all styles; mobile rules under `@media (max-width: 720px)` |
| `assets/globe/` | self-hosted three.js + textures |
| `tests/globe.test.mjs` | geography guard rails: `node --test scripts/tests/globe.test.mjs` |

## Behaviour

- **Desktop (hover: hover):** hover slows the spin and shows marker + panel; click pauses/resumes;
  drag rotates (horizontal = spin, vertical = tilt, clamped ±0.6 rad); releasing a drag outside the
  globe closes the panel. Click the marker for sunrise/sunset and "Use precise location".
- **Touch:** tap opens, tap again (or tap anywhere outside) closes; drag rotates (`touch-action: none`
  on the globe, so a swipe that starts on the 96 px globe does not scroll the page).
  A cancelled pointer is never treated as a tap.
- **Location:** browser time zone → approximate city (labelled **approx.**). Precise GPS only after
  the user clicks the button; denied / unavailable / timeout / unsupported / invalid fixes each show an
  explanation and keep the approximate position. Nothing is sent anywhere.
- **Sunrise/sunset** are shown in the device's time zone with its short name (a GPS fix far from
  the device's zone still displays device-local times, and says so).
- **Reduced motion:** no ambient spin or cloud drift; the scene renders only while the user drags or
  while hover/marker transitions play, then stops.

## Geography (verified by `globe.test.mjs`)

- Marker anchor = `(cosφ·cosλ, sinφ, −cosφ·sinλ)`, equal to `SphereGeometry`'s vertex for the equirectangular
  texel `u=(λ+180)/360, v=(φ+90)/180`. Initial `spin.y = −λ − π/2` turns the visitor's longitude to the camera.
- Sunrise/sunset match NOAA reference values within 4 min (Greenwich, New Delhi, Sydney); polar day/night → `null`.
- UTC offset comes from `Date#getTimezoneOffset` (DST aware); the time-zone name is canonicalised
  (`Asia/Calcutta` → `Asia/Kolkata`).

## Performance rules

- One render loop (`requestAnimationFrame`) that **stops** when off-screen (IntersectionObserver), tab hidden,
  or nothing is moving (paused/settled/reduced-motion). Easing snaps to its target so it can really stop.
- Panel clock is a 1 s interval that runs only while the panel is open and visible; the panel DOM is rebuilt
  only when its structure changes (otherwise only the time text is updated), so the button survives ticks.
- Canvas box is cached (ResizeObserver) — no layout reads per frame. `start()` is idempotent per host.

## Known limitations

- The day/night terminator is a fixed light direction, not the real sub-solar point (decorative).
- Only ~55 common IANA zones map to a city; any other zone shows the zone name with "no map position".
- City positions are centroids: an approximate marker can be a few hundred km from the visitor.
- Sunrise/sunset use the NOAA approximation (±~2 min, no refraction model beyond 90.833°, no altitude).
- No fallback image when WebGL is unavailable or the context is lost: the globe is hidden (`.rl-globe-off`).
- Not verifiable in the Claude Browser pane: real GPU load and 60 fps behaviour (the pane throttles
  `requestAnimationFrame` to ~1 fps); a real-device pass on a phone is still recommended.
