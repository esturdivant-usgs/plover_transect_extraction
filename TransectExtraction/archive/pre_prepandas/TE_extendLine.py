# From GIS stack exchange http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance

from math import hypot
import collections
from operator import add
import arcpy

#layer = arcpy.GetParameterAsText(0)
#distance = float(arcpy.GetParameterAsText(1))

# Added by EJS:
extendlength = 2000
rawtransects = 'LongIsland_LT'
arcpy.Project_management(rawtransects,rawtransects+'_temp6',nad83utm18)
rawtransects = rawtransects+'_temp6'
extendedTransects = site+"_extTrans_temp6"

arcpy.Project_management(rawtransects,rawtransects+'_temp7',nad83utm18)
layer = rawtransects+'_temp6'
distance = float(extendlength)

#def ExtendLine(lyrname,distance):
# Functions used to extend line
def newcoord(coords, dist):
    # Computes new coordinates x3,y3 at a specified distance along the prolongation of the line from x1,y1 to x2,y2
    (x1,y1),(x2,y2) = coords
    dx = x2 - x1
    dy = y2 - y1
    linelen = hypot(dx, dy)

    x3 = x2 + dx/linelen * dist
    y3 = y2 + dy/linelen * dist
    return x3, y3
def accumulate(iterable):
    # accumulate([1,2,3,4,5]) --> 1 3 6 10 15
    # Equivalent to itertools.accumulate() which isn't present in Python 2.7
    it = iter(iterable)
    total = next(it)
    yield total
    for element in it:
        total = add(total, element)
        yield total

# Will use OID to determine how to break up flat list of data by feature.
coordinates = [[row[0], row[1]] for row in arcpy.da.SearchCursor(layer, ["OID@", "SHAPE@XY"], explode_to_points=True)]
oid,vert = zip(*coordinates)
# Construct list of numbers that mark the start of a new feature class by counting OIDS and accumulating the values.
vertcounts = list(accumulate(collections.Counter(oid).values()))
#Grab the last two vertices of each feature
lastpoint = [point for x,point in enumerate(vert) if x+1 in vertcounts or x+2 in vertcounts]
# Obtain list of tuples of new end coordinates by converting flat list of tuples to list of lists of tuples.
newvert = [newcoord(y, distance) for y in zip(*[iter(lastpoint)]*2)]

j = 0
with arcpy.da.UpdateCursor(layer, "SHAPE@XY", explode_to_points=True) as rows:
    for i,row in enumerate(rows):
        if i+1 in vertcounts:
            row[0] = newvert[j]
            j+=1
            rows.updateRow(row)