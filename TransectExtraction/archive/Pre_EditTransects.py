"""
Edit LT transects
- fill in gaps along shoreline
- extend lines back behind
"""

import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

# Inputs
site = 'Assawoman'
year = '2012'
arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)

ShorelinePts = '{}{}_SLpts'.format(site,year)
MHW_oceanside = "{}{}_FullShoreline".format(site,year)
barrierBoundary = '{}{}_bndpoly'.format(site,year)

old_transects = '{}_LTtransects'.format(site)
new_transects = '{}_LTtrans_sort'.format(site)
extTransects = '{}_extTrans'.format(site)

# identify and fill gaps
"""
For each transect, find the distance to transect with TO=TO-1 and TO=TO+1
If the distance is greater than 50m, make more.
At each visually-apparent gap in the transects (any area where neighboring transects are greater than 50m apart),
I measured the gap along the shoreline (from lidar)
In an Edit session, I selected the appropriate number of neighboring transects to fill the gap ((gap_length/50)-1),
copied them, pasted them into the same feature class and then moved them to fill the gap as seamlessly as possible
(perpendicular to generalized shoreline, 50m gap between each transect)

"""

# reset TRANSORDER
arcpy.Sort_management(old_transects,new_transects,[['Shape','ASCENDING']],'LL') # Sort from lower left
with arcpy.da.UpdateCursor(new_transects,['OID@','TransOrder']) as cursor:
    for row in cursor:
        cursor.updateRow([row[0],row[0]])

# extend lines
ExtendLine(new_transects,extTransects,3000)

