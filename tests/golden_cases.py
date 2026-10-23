"""Golden cases: expected tags derived BY HAND from the raw S-57 attributes.

Each case cites the raw values (as read by GDAL, after UPDATES=APPLY) it was derived from.
Code meanings: GDAL s57expectedinput.csv; OSM values: OSM wiki Seamarks/* pages (see
enc2osm/mapping/values.yaml comments). Only `seamark:*` tags are compared (plus enc:lnam).
Derivation rules applied by hand: one unsectored light -> seamark:light:*, otherwise
seamark:light:N:* numbered by (unsectored first, SECTR1, colour, LNAM); SIGGRP "(x)" -> x;
numbers without trailing ".0"; MARSYS on buoys/beacons inherited from M_NSYS (all = 2, IALA B).
"""

SMALL, EXTRA = "tests/data/small", "tests/data/golden_extra"

CASES = [
    # 1 -------------------------------------------------------------------------------------
    dict(cell="US5OAKFG", lnam="0226014C1D810032", src=SMALL,
         raw="BOYLAT BOYSHP=4 CATLAM=1 COLOUR=[4] STATUS=[1] MARSYS=2(M_NSYS) "
             "OBJNAM='San Francisco Bay North Channel Lighted Buoy 1'; LIGHTS COLOUR=[4] "
             "EXCLIT=4 LITCHR=2 SIGGRP=(1) SIGPER=6.0 SIGSEQ=00.6+(05.4)",
         tags={"seamark:type": "buoy_lateral", "seamark:buoy_lateral:shape": "pillar",
               "seamark:buoy_lateral:category": "port", "seamark:buoy_lateral:colour": "green",
               "seamark:buoy_lateral:status": "permanent",
               "seamark:buoy_lateral:system": "iala-b",
               "seamark:name": "San Francisco Bay North Channel Lighted Buoy 1",
               "seamark:light:colour": "green", "seamark:light:exhibition": "night",
               "seamark:light:character": "Fl", "seamark:light:group": "1",
               "seamark:light:period": "6", "seamark:light:sequence": "00.6+(05.4)"}),
    # 2 preferred channel buoy with bell
    dict(cell="US5OAKFG", lnam="0226014C1D730032", src=SMALL,
         raw="BOYLAT BOYSHP=4 CATLAM=3 COLOUR=[4,3,4] COLPAT=[1] STATUS=[1] MARSYS=2; "
             "LIGHTS COLOUR=[4] EXCLIT=4 LITCHR=2 SIGGRP=(2+1) SIGPER=6.0 "
             "SIGSEQ=00.3+(00.4)+00.3+(01.2)+00.3+(03.5); FOGSIG CATFOG=7",
         tags={"seamark:type": "buoy_lateral", "seamark:buoy_lateral:shape": "pillar",
               "seamark:buoy_lateral:category": "preferred_channel_starboard",
               "seamark:buoy_lateral:colour": "green;red;green",
               "seamark:buoy_lateral:colour_pattern": "horizontal",
               "seamark:buoy_lateral:status": "permanent",
               "seamark:buoy_lateral:system": "iala-b",
               "seamark:name": "Alcatraz Lighted Bell Buoy AZ",
               "seamark:light:colour": "green", "seamark:light:exhibition": "night",
               "seamark:light:character": "Fl", "seamark:light:group": "2+1",
               "seamark:light:period": "6",
               "seamark:light:sequence": "00.3+(00.4)+00.3+(01.2)+00.3+(03.5)",
               "seamark:fog_signal:category": "bell"}),
    # 3 buoy with racon
    dict(cell="US5OAKFG", lnam="0226014C1D7F0032", src=SMALL,
         raw="BOYLAT BOYSHP=4 CATLAM=4 COLOUR=[3,4,3] COLPAT=[1] STATUS=[1] MARSYS=2; LIGHTS "
             "COLOUR=[3] EXCLIT=4 LITCHR=2 SIGGRP=(2+1) SIGPER=6.0 SIGSEQ=...; RTPBCN CATRTB=2 "
             "RADWAL=0.03-X SIGGRP=(K) STATUS=[1] OBJNAM='Harding Rock RACON'",
         tags={"seamark:type": "buoy_lateral", "seamark:buoy_lateral:shape": "pillar",
               "seamark:buoy_lateral:category": "preferred_channel_port",
               "seamark:buoy_lateral:colour": "red;green;red",
               "seamark:buoy_lateral:colour_pattern": "horizontal",
               "seamark:buoy_lateral:status": "permanent",
               "seamark:buoy_lateral:system": "iala-b",
               "seamark:name": "Harding Rock Light Buoy HR",
               "seamark:light:colour": "red", "seamark:light:exhibition": "night",
               "seamark:light:character": "Fl", "seamark:light:group": "2+1",
               "seamark:light:period": "6",
               "seamark:light:sequence": "00.3+(00.4)+00.3+(01.2)+00.3+(03.5)",
               "seamark:radar_transponder:category": "racon",
               "seamark:radar_transponder:wavelength": "0.03-X",
               "seamark:radar_transponder:group": "K",
               "seamark:radar_transponder:status": "permanent"}),
    # 4 safe water buoy, morse light, topmark
    dict(cell="US5OAKFG", lnam="0226E0F0CCE83039", src=SMALL,
         raw="BOYSAW BOYSHP=4 COLOUR=[3,1] COLPAT=[2] STATUS=[1] MARSYS=2; LIGHTS COLOUR=[1] "
             "EXCLIT=4 LITCHR=12 SIGGRP=(A) SIGPER=8.0 SIGSEQ=00.4+(00.6)+02.0+(05.0); "
             "TOPMAR COLOUR=[3] TOPSHP=3",
         tags={"seamark:type": "buoy_safe_water", "seamark:buoy_safe_water:shape": "pillar",
               "seamark:buoy_safe_water:colour": "red;white",
               "seamark:buoy_safe_water:colour_pattern": "vertical",
               "seamark:buoy_safe_water:status": "permanent",
               "seamark:buoy_safe_water:system": "iala-b",
               "seamark:name": "San Francisco Bay North Channel Lighted Buoy A",
               "seamark:light:colour": "white", "seamark:light:exhibition": "night",
               "seamark:light:character": "Mo", "seamark:light:group": "A",
               "seamark:light:period": "8", "seamark:light:sequence": "00.4+(00.6)+02.0+(05.0)",
               "seamark:topmark:colour": "red", "seamark:topmark:shape": "sphere"}),
    # 5 unlit special purpose can buoy
    dict(cell="US5OAKFG", lnam="0226014C1D8B0032", src=SMALL,
         raw="BOYSPP BOYSHP=2 CATSPM=[52] COLOUR=[6] OBJNAM=C STATUS=[8] MARSYS=2",
         tags={"seamark:type": "buoy_special_purpose", "seamark:buoy_special_purpose:shape": "can",
               "seamark:buoy_special_purpose:category": "unknown_purpose",
               "seamark:buoy_special_purpose:colour": "yellow",
               "seamark:buoy_special_purpose:status": "private",
               "seamark:buoy_special_purpose:system": "iala-b", "seamark:name": "C"}),
    # 6 lighted research buoy (no shape)
    dict(cell="US5OAKFG", lnam="022685498E887F83", src=SMALL,
         raw="BOYSPP CATSPM=[10] COLOUR=[6] STATUS=[8] INFORM=\"Buoy tethered to buoy 1 w/ 10' "
             "cable\" MARSYS=2; LIGHTS COLOUR=[6] LITCHR=2 SIGGRP=(1) SIGPER=2.5 "
             "SIGSEQ=00.3+(02.2)",
         tags={"seamark:type": "buoy_special_purpose",
               "seamark:buoy_special_purpose:category": "recording",
               "seamark:buoy_special_purpose:colour": "yellow",
               "seamark:buoy_special_purpose:status": "private",
               "seamark:buoy_special_purpose:information": "Buoy tethered to buoy 1 w/ 10' cable",
               "seamark:buoy_special_purpose:system": "iala-b",
               "seamark:name": "San Francisco Waterfront Lighted Research Buoy 1A",
               "seamark:light:colour": "yellow", "seamark:light:character": "Fl",
               "seamark:light:group": "1", "seamark:light:period": "2.5",
               "seamark:light:sequence": "00.3+(02.2)"}),
    # 7 lateral beacon with light and daymark
    dict(cell="US5OAKFG", lnam="0226011CA73C0032", src=SMALL,
         raw="BCNLAT BCNSHP=1 CATLAM=1 COLOUR=[4] STATUS=[1] MARSYS=2; LIGHTS COLOUR=[4] "
             "EXCLIT=4 HEIGHT=9.1 LITCHR=2 SIGGRP=(1) SIGPER=2.5 SIGSEQ=00.3+(02.2) VALNMR=3.0; "
             "DAYMAR COLOUR=[4,4] COLPAT=[6] TOPSHP=19",
         tags={"seamark:type": "beacon_lateral", "seamark:beacon_lateral:shape": "stake",
               "seamark:beacon_lateral:category": "port", "seamark:beacon_lateral:colour": "green",
               "seamark:beacon_lateral:status": "permanent",
               "seamark:beacon_lateral:system": "iala-b",
               "seamark:name": "San Francisco Bay North Channel Light 5",
               "seamark:light:colour": "green", "seamark:light:exhibition": "night",
               "seamark:light:height": "9.1", "seamark:light:character": "Fl",
               "seamark:light:group": "1", "seamark:light:period": "2.5",
               "seamark:light:sequence": "00.3+(02.2)", "seamark:light:range": "3",
               "seamark:daymark:colour": "green;green", "seamark:daymark:colour_pattern": "border",
               "seamark:daymark:shape": "square"}),
    # 8 private lateral beacon
    dict(cell="US5OAKFG", lnam="0226014C1D230032", src=SMALL,
         raw="BCNLAT BCNSHP=1 CATLAM=1 COLOUR=[4] STATUS=[8] MARSYS=2; LIGHTS COLOUR=[4] "
             "EXCLIT=4 HEIGHT=2.7 LITCHR=2 SIGGRP=(1) SIGPER=5.0 SIGSEQ=00.5+(04.5)",
         tags={"seamark:type": "beacon_lateral", "seamark:beacon_lateral:shape": "stake",
               "seamark:beacon_lateral:category": "port", "seamark:beacon_lateral:colour": "green",
               "seamark:beacon_lateral:status": "private",
               "seamark:beacon_lateral:system": "iala-b",
               "seamark:name": "San Francisco Marina West Basin Light 3",
               "seamark:light:colour": "green", "seamark:light:exhibition": "night",
               "seamark:light:height": "2.7", "seamark:light:character": "Fl",
               "seamark:light:group": "1", "seamark:light:period": "5",
               "seamark:light:sequence": "00.5+(04.5)"}),
    # 9 special purpose beacon, warning daymark (diamond)
    dict(cell="US5OAKFG", lnam="0226014C1D5C0032", src=SMALL,
         raw="BCNSPP BCNSHP=1 CATSPM=[27] STATUS=[1] MARSYS=2; LIGHTS COLOUR=[1] EXCLIT=4 "
             "HEIGHT=22.9 LITCHR=2 SIGGRP=(1) SIGPER=6.0 SIGSEQ=00.6+(05.4) VALNMR=7.0; DAYMAR "
             "CATSPM=[27] COLOUR=[1,3,1,1,3] COLPAT=[6,4] TOPSHP=12",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "stake",
               "seamark:beacon_special_purpose:category": "warning",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Yellow Bluff Light",
               "seamark:light:colour": "white", "seamark:light:exhibition": "night",
               "seamark:light:height": "22.9", "seamark:light:character": "Fl",
               "seamark:light:group": "1", "seamark:light:period": "6",
               "seamark:light:sequence": "00.6+(05.4)", "seamark:light:range": "7",
               "seamark:daymark:category": "warning",
               "seamark:daymark:colour": "white;red;white;white;red",
               "seamark:daymark:colour_pattern": "border;squared",
               "seamark:daymark:shape": "rhombus"}),
    # 10 beacon tower, quick light
    dict(cell="US5OAKFG", lnam="0226014C1D6F0032", src=SMALL,
         raw="BCNSPP BCNSHP=3 CATSPM=[27] STATUS=[1] MARSYS=2; LIGHTS COLOUR=[1] EXCLIT=4 "
             "HEIGHT=6.1 LITCHR=4 SIGGRP=(1) SIGPER=1.0 SIGSEQ=00.3+(00.7) VALNMR=4.0; DAYMAR "
             "CATSPM=[27] COLOUR=[1,3,1,1,3] COLPAT=[6,4] TOPSHP=12",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "tower",
               "seamark:beacon_special_purpose:category": "warning",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Anita Rock Light",
               "seamark:light:colour": "white", "seamark:light:exhibition": "night",
               "seamark:light:height": "6.1", "seamark:light:character": "Q",
               "seamark:light:group": "1", "seamark:light:period": "1",
               "seamark:light:sequence": "00.3+(00.7)", "seamark:light:range": "4",
               "seamark:daymark:category": "warning",
               "seamark:daymark:colour": "white;red;white;white;red",
               "seamark:daymark:colour_pattern": "border;squared",
               "seamark:daymark:shape": "rhombus"}),
    # 11 standalone floodlight + fog horn (no structure, no range -> light_minor)
    dict(cell="US5OAKFG", lnam="0226014C23010032", src=SMALL,
         raw="LIGHTS CATLIT=[8] EXCLIT=4 LITCHR=1 (no VALNMR); FOGSIG CATFOG=10 SIGGEN=3 "
             "SIGGRP=(2) SIGPER=30.0 SIGSEQ=02.0+(02.0)+02.0+(24.0) INFORM='Horn is activated...'",
         tags={"seamark:type": "light_minor", "seamark:light:category": "floodlight",
               "seamark:light:exhibition": "night", "seamark:light:character": "F",
               "seamark:fog_signal:category": "horn", "seamark:fog_signal:generation": "hand",
               "seamark:fog_signal:group": "2", "seamark:fog_signal:period": "30",
               "seamark:fog_signal:sequence": "02.0+(02.0)+02.0+(24.0)",
               "seamark:fog_signal:information": "Horn is activated by keying the mic 5 times on "
               "VHF-FM Ch 81A- horn will operate for thirty minutes."}),
    # 12 lighthouse: landmark tower + light + fog signal
    dict(cell="US5OAKFG", lnam="0226014E060A0032", src=SMALL,
         raw="LNDMRK CATLMK=[17] COLOUR=[1] CONVIS=1 FUNCTN=[33] STATUS=[1] INFORM='Square "
             "house'; LIGHTS COLOUR=[4] EXCLIT=4 HEIGHT=18.3 LITCHR=2 SIGGRP=(1) SIGPER=5.0 "
             "SIGSEQ=00.5+(04.5) VALNMR=4.0; FOGSIG CATFOG=10 SIGGEN=1 SIGGRP=(1) SIGPER=15.0 "
             "SIGSEQ=02.0+(13.0)",
         tags={"seamark:type": "landmark", "seamark:landmark:category": "tower",
               "seamark:landmark:colour": "white", "seamark:landmark:conspicuity": "conspicuous",
               "seamark:landmark:function": "light_support",
               "seamark:landmark:status": "permanent",
               "seamark:landmark:information": "Square house", "seamark:name": "Point Blunt Light",
               "seamark:light:colour": "green", "seamark:light:exhibition": "night",
               "seamark:light:height": "18.3", "seamark:light:character": "Fl",
               "seamark:light:group": "1", "seamark:light:period": "5",
               "seamark:light:sequence": "00.5+(04.5)", "seamark:light:range": "4",
               "seamark:fog_signal:category": "horn",
               "seamark:fog_signal:generation": "automatic", "seamark:fog_signal:group": "1",
               "seamark:fog_signal:period": "15", "seamark:fog_signal:sequence": "02.0+(13.0)"}),
    # 13 major lighthouse with emergency light (two unsectored lights -> numbered by LNAM)
    dict(cell="US5OAKFG", lnam="02262CBF08AA2715", src=SMALL,
         raw="LNDMRK CATLMK=[17] COLOUR=[7] CONVIS=1 FUNCTN=[33] VERLEN=25.6; "
             "LIGHTS 0226014C23340032 CATLIT=[17] COLOUR=[1] EXCLIT=4 HEIGHT=65.2 LITCHR=2 "
             "LITVIS=[5] SIGGRP=(1) SIGPER=5.0 SIGSEQ=00.5+(04.5) VALNMR=20.0 INFORM=...; "
             "LIGHTS 0226014E0B1B0032 COLOUR=[1] EXCLIT=4 HEIGHT=65.2 LITCHR=2 SIGGRP=(1) "
             "SIGPER=5.0 SIGSEQ=00.5+(04.5) VALNMR=20.0",
         tags={"seamark:type": "landmark", "seamark:landmark:category": "tower",
               "seamark:landmark:colour": "grey", "seamark:landmark:conspicuity": "conspicuous",
               "seamark:landmark:function": "light_support",
               "seamark:landmark:vertical_length": "25.6", "seamark:name": "Alcatraz Light",
               "seamark:light:1:category": "emergency", "seamark:light:1:colour": "white",
               "seamark:light:1:exhibition": "night", "seamark:light:1:height": "65.2",
               "seamark:light:1:character": "Fl", "seamark:light:1:visibility": "unintensified",
               "seamark:light:1:group": "1", "seamark:light:1:period": "5",
               "seamark:light:1:sequence": "00.5+(04.5)", "seamark:light:1:range": "20",
               "seamark:light:1:information": "Reduced intensity when main light is extingushed.",
               "seamark:light:2:colour": "white", "seamark:light:2:exhibition": "night",
               "seamark:light:2:height": "65.2", "seamark:light:2:character": "Fl",
               "seamark:light:2:group": "1", "seamark:light:2:period": "5",
               "seamark:light:2:sequence": "00.5+(04.5)", "seamark:light:2:range": "20"}),
    # 14 unlit landmark
    dict(cell="US5OAKFG", lnam="0226BC34589FA2D0", src=SMALL,
         raw="LNDMRK CATLMK=[17] CONVIS=1 OBJNAM='Coit Tower'",
         tags={"seamark:type": "landmark", "seamark:landmark:category": "tower",
               "seamark:landmark:conspicuity": "conspicuous", "seamark:name": "Coit Tower"}),
    # 15-16 wrecks
    dict(cell="US5OAKFG", lnam="02261923A17AA2D0", src=SMALL,
         raw="WRECKS CATWRK=2 EXPSOU=1 QUASOU=[6] VALSOU=4.7 WATLEV=3 (DUNI=1 m)",
         tags={"seamark:type": "wreck", "seamark:wreck:category": "dangerous",
               "seamark:wreck:depth": "4.7", "seamark:wreck:water_level": "submerged"}),
    dict(cell="US5OAKFG", lnam="02261B20B906A2D0", src=SMALL,
         raw="WRECKS CATWRK=1 EXPSOU=1 QUASOU=[6] VALSOU=24.9 WATLEV=3",
         tags={"seamark:type": "wreck", "seamark:wreck:category": "non-dangerous",
               "seamark:wreck:depth": "24.9", "seamark:wreck:water_level": "submerged"}),
    # 17-18 rocks
    dict(cell="US5OAKFG", lnam="022675E30C5AA2D0", src=SMALL,
         raw="UWTROC EXPSOU=1 OBJNAM='Blossom Rock' QUASOU=[6] VALSOU=11.8 WATLEV=3",
         tags={"seamark:type": "rock", "seamark:name": "Blossom Rock",
               "seamark:rock:depth": "11.8", "seamark:rock:water_level": "submerged"}),
    dict(cell="US5OAKFG", lnam="02260D03B698A2D0", src=SMALL,
         raw="UWTROC OBJNAM='Cone Rock' QUASOU=[2] WATLEV=4",
         tags={"seamark:type": "rock", "seamark:name": "Cone Rock",
               "seamark:rock:water_level": "covers"}),
    # 19-20 obstructions
    dict(cell="US5OAKFG", lnam="022602D30A24A2D0", src=SMALL,
         raw="OBSTRN CATOBS=1 CONDTN=2 QUASOU=[2] WATLEV=3",
         tags={"seamark:type": "obstruction", "seamark:obstruction:category": "stump",
               "seamark:obstruction:condition": "ruined",
               "seamark:obstruction:water_level": "submerged"}),
    dict(cell="US5OAKFG", lnam="0226F86570FDA2D0", src=SMALL,
         raw="OBSTRN EXPSOU=1 QUASOU=[6] VALSOU=56.9 WATLEV=3 INFORM='Current meter'",
         tags={"seamark:type": "obstruction", "seamark:obstruction:depth": "56.9",
               "seamark:obstruction:water_level": "submerged",
               "seamark:obstruction:information": "Current meter"}),
    # 21 mooring buoy, 22 pile
    dict(cell="US5OAKFG", lnam="02260FB4E1A512E3", src=SMALL,
         raw="MORFAC CATMOR=7 COLOUR=[1,5] COLPAT=[1] "
             "OBJNAM='Sausalito Coast Guard Mooring Buoy 1'",
         tags={"seamark:type": "mooring", "seamark:mooring:category": "buoy",
               "seamark:mooring:colour": "white;blue", "seamark:mooring:colour_pattern":
               "horizontal", "seamark:name": "Sausalito Coast Guard Mooring Buoy 1"}),
    dict(cell="US5OAKFG", lnam="02260B22D3D2A2D0", src=SMALL,
         raw="PILPNT CATPLE=3",
         tags={"seamark:type": "pile", "seamark:pile:category": "post"}),
    # 23 north cardinal buoy with topmark
    dict(cell="US3WA1EF", lnam="022601A25F670032", src=EXTRA,
         raw="BOYCAR BOYSHP=4 CATCAM=1 COLOUR=[2,6] COLPAT=[1] OBJNAM=VK STATUS=[1] MARSYS=2; "
             "LIGHTS COLOUR=[1] LITCHR=4 SIGGRP=(1) SIGPER=1.0 SIGSEQ=00.3+(00.7); "
             "TOPMAR COLOUR=[2] TOPSHP=13",
         tags={"seamark:type": "buoy_cardinal", "seamark:buoy_cardinal:shape": "pillar",
               "seamark:buoy_cardinal:category": "north",
               "seamark:buoy_cardinal:colour": "black;yellow",
               "seamark:buoy_cardinal:colour_pattern": "horizontal",
               "seamark:buoy_cardinal:status": "permanent",
               "seamark:buoy_cardinal:system": "iala-b", "seamark:name": "VK",
               "seamark:light:colour": "white", "seamark:light:character": "Q",
               "seamark:light:group": "1", "seamark:light:period": "1",
               "seamark:light:sequence": "00.3+(00.7)",
               "seamark:topmark:colour": "black", "seamark:topmark:shape": "2 cones up"}),
    # 24 isolated danger buoy
    dict(cell="US3WA1EF", lnam="022600136CE40001", src=EXTRA,
         raw="BOYISD BOYSHP=4 COLOUR=[2,3,2] COLPAT=[1] STATUS=[1] INFORM='Rock has depth of 2½ "
             "fathoms over it.' MARSYS=2; LIGHTS COLOUR=[1] EXCLIT=4 LITCHR=2 SIGGRP=(2) "
             "SIGPER=5.0 SIGSEQ=00.4+(00.6)+00.4+(03.6)",
         tags={"seamark:type": "buoy_isolated_danger",
               "seamark:buoy_isolated_danger:shape": "pillar",
               "seamark:buoy_isolated_danger:colour": "black;red;black",
               "seamark:buoy_isolated_danger:colour_pattern": "horizontal",
               "seamark:buoy_isolated_danger:status": "permanent",
               "seamark:buoy_isolated_danger:information": "Rock has depth of 2½ fathoms over it.",
               "seamark:buoy_isolated_danger:system": "iala-b",
               "seamark:name": "Reid Rock Isolated Danger Lighted Buoy DR",
               "seamark:light:colour": "white", "seamark:light:exhibition": "night",
               "seamark:light:character": "Fl", "seamark:light:group": "2",
               "seamark:light:period": "5", "seamark:light:sequence": "00.4+(00.6)+00.4+(03.6)"}),
    # 25 unlit daybeacon on pile with radar reflector
    dict(cell="US3WA1EF", lnam="022600136CC40001", src=EXTRA,
         raw="BCNLAT BCNSHP=5 CATLAM=1 COLOUR=[4] CONRAD=3 STATUS=[1] MARSYS=2; DAYMAR "
             "COLOUR=[4,4] COLPAT=[4] TOPSHP=19",
         tags={"seamark:type": "beacon_lateral", "seamark:beacon_lateral:shape": "pile",
               "seamark:beacon_lateral:category": "port", "seamark:beacon_lateral:colour": "green",
               "seamark:beacon_lateral:reflectivity": "reflector",
               "seamark:beacon_lateral:status": "permanent",
               "seamark:beacon_lateral:system": "iala-b",
               "seamark:name": "Minnesota Reef Daybeacon 1",
               "seamark:daymark:colour": "green;green", "seamark:daymark:colour_pattern": "squared",
               "seamark:daymark:shape": "square"}),
    # 26 two sector lights (main + emergency), numbered by SECTR1
    dict(cell="US3WA1EF", lnam="02260001850A0001", src=EXTRA,
         raw="BCNSPP BCNSHP=4 CATSPM=[27] COLOUR=[3] STATUS=[1] MARSYS=2; LIGHTS COLOUR=[1] "
             "EXCLIT=4 HEIGHT=36.9 LITCHR=2 SECTR1=149 SECTR2=60 SIGGRP=(1) SIGPER=15 VALNMR=17; "
             "LIGHTS CATLIT=[17] COLOUR=[3] EXCLIT=4 HEIGHT=31.1 LITCHR=1 SECTR1=156 "
             "SECTR2=211.5 VALNMR=8",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "lattice",
               "seamark:beacon_special_purpose:category": "warning",
               "seamark:beacon_special_purpose:colour": "red",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Saturna Island Light",
               "seamark:light:1:colour": "white", "seamark:light:1:exhibition": "night",
               "seamark:light:1:height": "36.9", "seamark:light:1:character": "Fl",
               "seamark:light:1:sector_start": "149", "seamark:light:1:sector_end": "60",
               "seamark:light:1:group": "1", "seamark:light:1:period": "15",
               "seamark:light:1:range": "17",
               "seamark:light:2:category": "emergency", "seamark:light:2:colour": "red",
               "seamark:light:2:exhibition": "night", "seamark:light:2:height": "31.1",
               "seamark:light:2:character": "F", "seamark:light:2:sector_start": "156",
               "seamark:light:2:sector_end": "211.5", "seamark:light:2:range": "8"}),
    # 27 four-sector light
    dict(cell="US3WA1EF", lnam="022601A2486E0032", src=EXTRA,
         raw="BCNSPP BCNSHP=3 COLOUR=[1] CONRAD=1 STATUS=[1] INFORM=Round MARSYS=2; 4x LIGHTS "
             "LITCHR=4 SIGGRP=(1) SIGPER=1.0 SIGSEQ=00.3+(00.7) VALNMR=7 EXCLIT=4: "
             "R 13.2-62 h7 / W 62-170.3 h7 / W 170.3-216 (no HEIGHT) / W 216-13.3 h7",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "tower",
               "seamark:beacon_special_purpose:colour": "white",
               "seamark:beacon_special_purpose:reflectivity": "conspicuous",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:information": "Round",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Fiddle Reef Light",
               **{f"seamark:light:{i}:{k}": v for i in (1, 2, 3, 4) for k, v in {
                   "exhibition": "night", "character": "Q", "group": "1", "period": "1",
                   "sequence": "00.3+(00.7)", "range": "7"}.items()},
               "seamark:light:1:colour": "red", "seamark:light:1:height": "7",
               "seamark:light:1:sector_start": "13.2", "seamark:light:1:sector_end": "62",
               "seamark:light:2:colour": "white", "seamark:light:2:height": "7",
               "seamark:light:2:sector_start": "62", "seamark:light:2:sector_end": "170.3",
               "seamark:light:3:colour": "white",
               "seamark:light:3:sector_start": "170.3", "seamark:light:3:sector_end": "216",
               "seamark:light:4:colour": "white", "seamark:light:4:height": "7",
               "seamark:light:4:sector_start": "216", "seamark:light:4:sector_end": "13.3"}),
    # 28 all-round light + narrow red sector (unsectored first)
    dict(cell="US3WA1EF", lnam="0226147888FC117A", src=EXTRA,
         raw="BCNSPP BCNSHP=4 CATSPM=[27] COLOUR=[2] NATCON=[7] STATUS=[1] INFORM='Cylindrical "
             "base' MARSYS=2; LIGHTS W EXCLIT=4 HEIGHT=6.7 LITCHR=2 SIGGRP=(1) SIGPER=2.5 "
             "SIGSEQ=00.3+(02.2) VALNMR=7; LIGHTS R SECTR1=173.5 SECTR2=176.5 (same rhythm); "
             "DAYMAR COLOUR=[1,2,1,1,2] COLPAT=[6,4] TOPSHP=12",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "lattice",
               "seamark:beacon_special_purpose:category": "warning",
               "seamark:beacon_special_purpose:colour": "black",
               "seamark:beacon_special_purpose:construction": "metal",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:information": "Cylindrical base",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Belle Rock Sector Light",
               **{f"seamark:light:{i}:{k}": v for i in (1, 2) for k, v in {
                   "exhibition": "night", "height": "6.7", "character": "Fl", "group": "1",
                   "period": "2.5", "sequence": "00.3+(02.2)", "range": "7"}.items()},
               "seamark:light:1:colour": "white", "seamark:light:2:colour": "red",
               "seamark:light:2:sector_start": "173.5", "seamark:light:2:sector_end": "176.5",
               "seamark:daymark:colour": "white;black;white;white;black",
               "seamark:daymark:colour_pattern": "border;squared",
               "seamark:daymark:shape": "rhombus"}),
    # 29 lighthouse with a single sector light -> numbered
    dict(cell="US3WA1EF", lnam="02260006C1770001", src=EXTRA,
         raw="LNDMRK CATLMK=[17] COLOUR=[1] CONVIS=1 FUNCTN=[33] HEIGHT=10.7 STATUS=[1] "
             "INFORM=Round; LIGHTS COLOUR=[1] EXCLIT=4 HEIGHT=17.4 LITCHR=2 LITVIS=[4] SECTR1=55 "
             "SECTR2=252.4 SIGGRP=(1) SIGPER=10 SIGSEQ=01.0+(09.0) VALNMR=17 "
             "INFORM='superimposed every 10s'",
         tags={"seamark:type": "landmark", "seamark:landmark:category": "tower",
               "seamark:landmark:colour": "white", "seamark:landmark:conspicuity": "conspicuous",
               "seamark:landmark:function": "light_support", "seamark:landmark:height": "10.7",
               "seamark:landmark:status": "permanent", "seamark:landmark:information": "Round",
               "seamark:name": "Active Pass Light",
               "seamark:light:1:colour": "white", "seamark:light:1:exhibition": "night",
               "seamark:light:1:height": "17.4", "seamark:light:1:character": "Fl",
               "seamark:light:1:visibility": "intensified",
               "seamark:light:1:sector_start": "55", "seamark:light:1:sector_end": "252.4",
               "seamark:light:1:group": "1", "seamark:light:1:period": "10",
               "seamark:light:1:sequence": "01.0+(09.0)", "seamark:light:1:range": "17",
               "seamark:light:1:information": "superimposed every 10s"}),
    # 30 range rear light: leading + rear, isophase, sector
    dict(cell="US4CA2CK", lnam="0226004B446F0EDF", src=SMALL,
         raw="BCNSPP BCNSHP=1 CATSPM=[16] STATUS=[1] MARSYS=2; LIGHTS CATLIT=[4,13] COLOUR=[4] "
             "EXCLIT=4 HEIGHT=16.8 LITCHR=7 SECTR1=54 SECTR2=62 SIGGRP=(1) SIGPER=6 "
             "SIGSEQ=03.0+(03.0); DAYMAR COLOUR=[3,1,3] COLPAT=[2] TOPSHP=21",
         tags={"seamark:type": "beacon_special_purpose",
               "seamark:beacon_special_purpose:shape": "stake",
               "seamark:beacon_special_purpose:category": "leading",
               "seamark:beacon_special_purpose:status": "permanent",
               "seamark:beacon_special_purpose:system": "iala-b",
               "seamark:name": "Pinole Shoal Range Rear Light",
               "seamark:light:1:category": "leading;rear", "seamark:light:1:colour": "green",
               "seamark:light:1:exhibition": "night", "seamark:light:1:height": "16.8",
               "seamark:light:1:character": "Iso", "seamark:light:1:sector_start": "54",
               "seamark:light:1:sector_end": "62", "seamark:light:1:group": "1",
               "seamark:light:1:period": "6", "seamark:light:1:sequence": "03.0+(03.0)",
               "seamark:daymark:colour": "red;white;red", "seamark:daymark:colour_pattern":
               "vertical", "seamark:daymark:shape": "rectangle, vertical"}),
    # 31 standalone major light (VALNMR 17 >= 10) with emergency light
    dict(cell="US2PACUY", lnam="0226004171960F4A", src=SMALL,
         raw="LIGHTS COLOUR=[1] EXCLIT=4 HEIGHT=27.1 LITCHR=8 SIGGRP=(1) SIGPER=4 "
             "SIGSEQ=(01.0)+03.0 VALNMR=17; LIGHTS 02260152ED260032 CATLIT=[17] same + LITVIS=[5] "
             "INFORM='Reduced intensity when main light is extinguished'",
         tags={"seamark:type": "light_major",
               **{f"seamark:light:{i}:{k}": v for i in (1, 2) for k, v in {
                   "colour": "white", "exhibition": "night", "height": "27.1", "character": "Oc",
                   "group": "1", "period": "4", "sequence": "(01.0)+03.0", "range": "17"}.items()},
               "seamark:light:2:category": "emergency",
               "seamark:light:2:visibility": "unintensified",
               "seamark:light:2:information": "Reduced intensity when main light is extinguished"}),
    # 32 dolphin, 33 rock with surface, 34 named deep obstruction (NINFOM unmapped)
    dict(cell="US3WA1EF", lnam="022611710D00E2FD", src=EXTRA,
         raw="MORFAC CATMOR=1 WATLEV=2 INFORM=Dols",
         tags={"seamark:type": "mooring", "seamark:mooring:category": "dolphin",
               "seamark:mooring:water_level": "dry", "seamark:mooring:information": "Dols"}),
    dict(cell="US3WA1EF", lnam="022602516C56E2FD", src=EXTRA,
         raw="UWTROC NATSUR=[9] QUASOU=[2] WATLEV=4",
         tags={"seamark:type": "rock", "seamark:rock:surface": "rocky",
               "seamark:rock:water_level": "covers"}),
    dict(cell="US3WA1EF", lnam="022694059A6DE2FD", src=EXTRA,
         raw="OBSTRN EXPSOU=2 OBJNAM='Venus Project' VALSOU=296.0 WATLEV=3 INFORM='submerged "
             "mooring buoy' NINFOM=...",
         tags={"seamark:type": "obstruction", "seamark:name": "Venus Project",
               "seamark:obstruction:depth": "296", "seamark:obstruction:water_level": "submerged",
               "seamark:obstruction:information": "submerged mooring buoy"}),
]
