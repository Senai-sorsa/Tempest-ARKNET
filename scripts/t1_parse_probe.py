"""T1 step 0 probe: decode one NCEI 1-s radiosonde BUFR with eccodes, print level count, heights, and key names."""
import sys
import numpy as np
from eccodes import *
f = open(sys.argv[1], "rb")
h = codes_bufr_new_from_file(f)
codes_set(h, "unpack", 1)
for k in ("stationNumber", "wmoBlockNumber", "wmoStationNumber", "latitude", "longitude", "typicalDate", "typicalTime", "radiosondeType"):
    try: print(k, codes_get(h, k))
    except Exception as e: pass
for k in ("nonCoordinatePressure", "pressure", "airTemperature", "windSpeed", "windDirection", "nonCoordinateGeopotentialHeight", "geopotentialHeight", "latitudeDisplacement", "timePeriod"):
    try:
        a = np.array(codes_get_array(h, k), float); a[a > 1e30] = np.nan
        print(k, a.size, np.nanmin(a), np.nanmax(a))
    except Exception as e: print(k, "-", type(e).__name__)
