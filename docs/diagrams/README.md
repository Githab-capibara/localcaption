# Diagrams

Rendered architecture and flow diagrams for the docs and the repository
README.

| Asset | Source (`.mmd`) | Rendered |
|---|---|---|
| Module architecture | [architecture.mmd](architecture.mmd) | [architecture.png](architecture.png) · [architecture.svg](architecture.svg) |
| Pipeline overview | [pipeline.mmd](pipeline.mmd) | [pipeline.png](pipeline.png) · [pipeline.svg](pipeline.svg) |
| Runtime sequence | [sequence.mmd](sequence.mmd) | [sequence.png](sequence.png) · [sequence.svg](sequence.svg) |
| Model routing split (donut) | — | [model-routing.svg](model-routing.svg) |

## Regenerating

`.mmd` files are the source of truth; `.png`/`.svg` are rendered from them
with Mermaid CLI (white background so they read in GitHub dark mode):

```bash
mmdc -i docs/diagrams/<name>.mmd -o docs/diagrams/<name>.png \
  -t default -b white --width 1600 --scale 2
mmdc -i docs/diagrams/<name>.mmd -o docs/diagrams/<name>.svg \
  -t default -b white --width 1600
```

`model-routing.svg` is drawn by hand (annotation cloud) and mirrors
`docs/adr/01-language-routing.md`.

Template: [template.md](template.md).