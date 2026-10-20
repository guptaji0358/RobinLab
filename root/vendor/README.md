# Vendored browser libraries

## pptx-preview 1.0.7

- Source: <https://www.npmjs.com/package/pptx-preview>
- File: `pptx-preview.umd.js` (unmodified build from the npm package)
- License: free to use, including commercially, per the package README
- Used by: `js/presentations.js` to render `.pptx` decks client-side

The script is loaded lazily — only when a visitor opens a deck — so it never
affects the home page or the Collection page. To update, replace the file with a
newer `dist/pptx-preview.umd.js` from the npm package; the global is
`window.pptxPreview` with `init(element, { width, height })` and
`preview(arrayBuffer)`.
