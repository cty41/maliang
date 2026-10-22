# Gallery thumbnail attribution

Every PNG in `thumbs/` is a modified derivative of an image by **cty41**,
licensed **CC BY 4.0** ([license text](../../LICENSES/CC-BY-4.0.txt)).
`thumbs.json` lists each source path and SHA-256; the sources keep their own
attribution files:

- Little Orange: [examples/little-orange](../../examples/little-orange/README.md)
- Falcon and crested goshawk: [examples/art-pilot/ATTRIBUTION.md](../../examples/art-pilot/ATTRIBUTION.md)
- Five-red Chow Poet: [examples/poet-cast/ATTRIBUTION.md](../../examples/poet-cast/ATTRIBUTION.md)
- Red Shiba Amazon: [examples/tactics-amazon/ATTRIBUTION.md](../../examples/tactics-amazon/ATTRIBUTION.md)

Modifications, made by [build_thumbs.py](build_thumbs.py): for the falcon and
crested goshawk only, pixels close to the magenta corner color are made
transparent for display; transparent margins are cropped; the image is scaled
with LANCZOS to fit 448x328 and centred on a 480x360 `#F4F1EA` background. The
thumbnails are display copies, not production candidates or review evidence.
Rerun `python docs/gallery/build_thumbs.py` to rebuild them and `thumbs.json`.

The build script and `thumbs.json` are MIT licensed like the rest of `docs/`.
