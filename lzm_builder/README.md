# LZM Builder

An attempt to reverse engineer the generation of .lzm files to use on
Lezyne GPS devices.

The main focus here is to generate .lzm files on your local machine and not
have to use the gpsroot.com interface. This will give you better flexbility
and all you to make custom maps for regions and areas.

## Requirements

- Python 3.8+
- `pip install -r requirements.txt`
  - osmium
- A base map in .pbf format
- osmium cli tools installed (if you want to use the extract method)
  - `brew install osmium-tool` (MacOS)

In order to generate a .lzm you will need a base map in .pbf format. You can
download these from [Geofabrik](https://download.geofabrik.de/) or
[BBBike](https://extract.bbbike.org/).

Geo 2 Day is my personal favourite: https://geo2day.com/

There is a sample pbf map file included in this repo for testing. It is an OpenStreetMap extract for the region around Signal du Botrange in Belgium. The highest point in Belgium with lots of cycling routes and hiking trails.

## Testing

There is a test script included that will generate a .lzm file for a small area around the Signal du Botrange. This is a good way to test that everything is working. I still can't guarantee that the resulting .lzm will work on your device. But it should. Someday Lezyne engineers will need to verify that this is correct. For now it works on my Super Pro GPS. 

```bash
python lzm_builder_test.py
```

## Usage

```bash
python lzm_builder.py --pbf map.osm.pbf --bbox 50.92,4.80,50.97,4.85 --verbose
```

The result will be a file called `mf_50.92_4.80_50.97_4.85.lzm` in the current directory.

Your bbox coordinates should include data that is in your base map. Otherwise you will get an empty lzm file.

Once you have generated .lzm files you can copy them to your Lezyne GPS device and use them in the same way as maps downloaded from gpsroot.com. Copy the .lzm files to the `Maps/` directory on your device.

## Considerations

If you intend to generate .lzm files for a small area of "Northern Italy" you should use a smaller regional base map that includes that area. If you use a base map for "Europe" or "World" it will take a lot longer to process.

At present (2025-10-08) the code only makes the the Polyline structures and does not include any Points of Interest (POI) or routing information. Nor does it make any file meta data for the .lzm files. This is a work in progress. The resulting .lzm simply loads into the device and you can see the map.

## Code Structure

The code has been refactored into multiple modules for better organization and maintainability.

`lzm_builder.py` is the main orchestrator that ties everything together.

The other files contain structures, classes, and functions for specific tasks.

## How this was Made

To give you some context, AI and myself made this by reverse engineering .lzm files from gpsroot.com. I used AI vibe coding and python to break apart the binary format and very small "known" simple maps of areas around my house. I have an old XOSS gps device that I assumed used a similar approach of the encoding, tiles, and compression. With Hex Fiend in MacOS I was able to see and report back to the AI the binary/hex and then the structured sections in the files. With a bit of trial and error the AI and I were able to figure out how the polylines were encoded. Many iterations and many claude code credits were used to get to this point. The major break through came when I made .lzm from gpsroot that had just one street going north and south in it and known longitude. This let me generate a fake street near my home going north south and have it show up on the device. After that then it was a matter of getting the data from OpenStreetMap and into the right format (.pbf). Then filtering it by bounding box and types.

I still have 0 clue if this is actually close to what the Lezyne team uses to generate their .lzm files. But it works well enough for me to make custom maps for my rides and hikes. I would assume that their source code is in C++ and not python. 

## Future Plans

At this point I have what I am mostly interested in. A way to make offline maps for my Lezyne GPS device.

I have made a script to generate a whole map of Belgium by splitting it into a grid of bounding boxes and generating a .lzm for each box. I loaded the entire Belgium.pbf file into memory and then processed each box. This took about 17 minutes to generate 73 .lzm files covering the whole country. I then copied them to my Lezyne device and it works great. So my next step is to focus on making large sets of .lzm files for larger areas. 

Then, my next idea is to bring in a GPX file of a planned bikepacking route and generate a .lzm file or files that include the route and just the area around the route. This would be a great way to make a custom offline maps for a specific ride or hike.

How cool would it be to autmatically export from Komoot: A gpx file of a route + a set of .lzm files for the area around the route. Then put that on the device ready to ride!

## Final Thoughts

I know that Lezyne is intending to discontinue their GPS devices in the near future. I have a number of their other products such as lights, bottle cages, multi tools, pumps, etc. I really like their products and have been using them for years. I hope that they continue to support their GPS devices for a while longer. But even if they don't, at least I have a way to make custom maps for my existing device. I am certain that my Lezyne Super Pro GPS will last me for many years to come. I think their GPS devices are the victims of competitors flooding the market with needless and useless marketing hype and features, like colors, touch screens, strava KOM auto matic uploading, and other nonsense. I just want a simple reliable GPS device that I can use for navigation. The Lezyne Super Pro GPS does that very well. 