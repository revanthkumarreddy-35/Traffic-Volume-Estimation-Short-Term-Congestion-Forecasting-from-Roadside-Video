# Camera 2 gate-placement example

Created 1 November 2026 using the built-in image_gen tool and the imagegen skill.

This is an AI-annotated teaching illustration based on the user's Screenshot (102).png. It is not a raw reference frame or a calibrated coordinate file. Do not use the generated photo or its pixels as input to counting or evaluation. Use the actual reference frame from the notebook to set precise gates.

- A spans the left road; its inside point is to the right, toward the junction.
- B spans the upper road; its inside point is below, toward the junction.
- C spans the right road; its inside point is to the left, toward the junction.
- Yellow endpoints a/b define each finite line; green arrows/dots show the junction side, not vehicle travel directions.
- Gates must span the traffic lanes. Confirm positions and directions on annotated pilot videos.

## Initial prompt

Use case: scientific-educational / infographic-diagram.
Edit target: the supplied screenshot of camera Norman Niles #2. Create one clear instructional example showing road-arm gate calibration for this SAME junction.
Crop away browser chrome and player controls, keeping only the original camera picture (roughly screenshot pixel rectangle x=413..1488, y=323..928), then add a clean title strip above and a legend below. Preserve the photographed junction geometry, vehicle locations and road markings. Do not invent roads or new cars. No triangle across the grass.
Draw exactly THREE thick yellow finite gates ACROSS the separate road arms, with visible circular endpoints labelled small lowercase a and b. Positions are approximate illustrative positions, not certified calibration:
A across the LEFT road, near 9% of cropped picture width, from about 44% to 63% of cropped picture height. Label "A: Left road".
B across the UPPER road, about 36% of cropped picture height, from about 21% to 32% of cropped picture width, ABOVE the central traffic island. Label "B: Upper road".
C across the RIGHT road, near 79% of cropped picture width, from about 50% to 71% of cropped picture height. Label "C: Right road".
The gates must not intersect and each must span the relevant road cross-section. Keep labels readable with dark semi-transparent backing, and do not cover the gate itself.
For EACH gate add one short GREEN arrow from its midpoint toward the junction side, ending in a green dot marked "inside": A points rightward, B points downward toward the intersection, C points leftward. These green arrows indicate calibration orientation, NOT a vehicle route. Do not add other road gates.
Title verbatim: "Example: three road-arm gates"
Legend verbatim: "Yellow line = gate (a to b)" and "Green arrow/dot = junction side (inside)".
Footer verbatim: "A → B: left to upper road    |    A → C: left to right road"
Small note: "Illustration only. Check exact positions on your notebook reference frame."
Produce a large, crisp landscape educational image. The original photo is the background, the overlays are clean flat vector-like annotations.

## Correction prompt

Edit only the GREEN arrow, green dot and 'inside' label belonging to C: Right road in this instructional image. They currently incorrectly point RIGHT, away from the junction. Remove that right-pointing C green arrow/dot/label completely. Replace them with a short GREEN arrow originating at the midpoint of C's yellow gate and pointing LEFT, ending at a green dot on the LEFT side of the yellow gate, toward the central junction. Put the green text 'inside' beside this new dot, also entirely LEFT of gate C. In this image's 1672x940 coordinates, C gate midpoint is around (1290,565); green arrow should go from approximately (1290,565) to (1220,565), with green dot centered about (1195,565). Make the left arrowhead unambiguous. Keep the yellow C line, its a/b endpoints, labels A/B/C, all other arrows, all wording, layout, photo and vehicle positions exactly unchanged. No extra arrow or inside marker on the right of gate C.
