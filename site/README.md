# QuorumRelay site

The static project site lives here. It renders the maintained repository Markdown as complete navigable documentation pages and bundles Mermaid locally for diagrams; it does not load a CDN or external font. Links use relative paths for the GitHub Pages project subpath.

```sh
cd site
npm ci
npm run dev      # build and serve at http://127.0.0.1:4173/quorumrelay/
npm run build    # output: site/dist
npm run preview  # serve the existing build
```

The Pages workflow builds on the default branch and deploys `site/dist`. Add documentation to the `entries` list in `build.mjs`; edit its source Markdown rather than generated pages. `DESIGN.md` describes the visual tokens. The user manual, developer guide and architecture must be present for the final release build.
