"""
Created by: Emily Sturdivant (esturdivant@usgs.gov)
Date: February 3, 2017


This routine preprocesses extended transects with correctly sort_IDs
"""
import os
import sys
import time
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# path to TransectExtraction module
if sys.platform == 'win32':
    script_path = r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction"
    sys.path.append(script_path) # path to TransectExtraction module
    import arcpy
    import pythonaddins
    from TE_functions_arcpy import *
if sys.platform == 'darwin':
    script_path = '/Users/esturdivant/GitHub/plover_transect_extraction/TransectExtraction'
    sys.path.append(script_path)
from TE_config import *
from TE_functions import *


# Create extendedTrans, LT transects with gaps filled and lines extended
# 1. Copy only the geometry of transects to use as material for filling gaps
extTrans14 = '{site}2014_extTrans'.format(**SiteYear_strings)
extTrans12 = '{site}2012_extTrans'.format(**SiteYear_strings)
arcpy.env.workspace = os.path.join(site_dir, '2014', 'Smith2014.gdb')
arcpy.FeatureClassToFeatureClass_conversion(extTrans14, home, extTrans12)
arcpy.env.workspace = home
trans_presort = 'trans_presort_temp'
CopyAndWipeFC(extTrans12, trans_presort, ['sort_ID'])
pythonaddins.MessageBox("Now we'll stop so you can copy existing groups of transects to fill in the gaps. If possible avoid overlapping transects", "Created {}. Proceed with manual processing.".format(trans_presort), 0)
exit()
# Remove manual transects from original
arcpy.SelectLayerByLocation_management(extTrans12, "ARE_IDENTICAL_TO",  trans_presort)
if int(arcpy.GetCount_management(trans_presort)[0]):
    # if old trans in new trans, delete them
    arcpy.DeleteFeatures_management(extTrans12)
arcpy.Append_management(trans_presort, extTrans12)









# TRANSECTS - extTrans_tidy
if not t_trans:
    print("Manual work seems necessary to remove transect overlap")
    print("Select the boundary lines between groups of overlapping transects")
    # Select the boundary lines between groups of overlapping transects
    exit()
if not t_trans:
    # Copy only the selected lines
    overlapTrans_lines = 'overlapTrans_lines_temp'
    arcpy.CopyFeatures_management(extendedTransects, overlapTrans_lines)
    arcpy.SelectLayerByAttribute_management(extendedTransects, "CLEAR_SELECTION")
    # Split transects at the lines of overlap.
    trans_x = 'overlap_points_temp'
    arcpy.Intersect_analysis([extendedTransects, overlapTrans_lines], trans_x,
                             'ALL', output_type="POINT")
    arcpy.SplitLineAtPoint_management(extendedTransects, trans_x, extTrans_tidy)
    exit()
if not t_trans:
    arcpy.DeleteFeatures_management(extTrans_tidy)
    arcpy.CopyFeatures_management(extTrans_tidy, extTrans_tidy_archive)









"""
SET VALUES
"""
trans_orig = os.path.join(home, "{site}_LTorig_utm".format(**SiteYear_strings))
trans_presort = "trans_presort"
trans_sort_1 = "{site}_trans_sorted".format(**SiteYear_strings)
trans_out = "{site}_extTrans".format(**SiteYear_strings)
trans_temp = "trans_temp"
sortfield = 'sort_ID'
trans_orig = SetInputFCname(home, 'Original National Assessment Transects', trans_orig)
"""
PROCESSING
"""
# TRANSECTS
"""
#rawtransects = SetInputFCname(home, 'Raw transects', 'rawtransects')
# Extend original transects to bay line if not already
if arcpy.Exists(gen_bay_line):
    # Select lines based on azimuth... so that they will not end up intersecting each other.
    # Select lines that still need to be extended. Include in selection the generalized bay line.
    arcpy.Merge_management([rawtransects, gen_bay_line],trans_temp)
    #arcpy.CopyFeatures_management(rawtransects, trans_temp)
    arcpy.ExtendLine_edit(trans_temp, extend_to="FEATURE")
    # un-select generalized bay line
    arcpy.DeleteFeatures_management(rawtransects)
    arcpy.Append_management(trans_temp, rawtransects)
    exit()
else:
    ExtendLine(rawtransects,extendedTransects,extendlength,proj_code)
    if len(arcpy.ListFields(extendedTransects,'OBJECTID*')) == 2:
        ReplaceFields(extendedTransects,{'OBJECTID':'OID@'})
"""
CopyAndWipeFC(trans_orig, trans_presort)
pythonaddins.MessageBox("Now we'll stop so you can copy existing groups of transects to fill in the gaps. If possible avoid overlapping transects", "Created {}. Proceed with manual processing.".format(trans_presort), 0)
exit()

# Delete any NAT transects in the new transects layer
arcpy.SelectLayerByLocation_management(trans_presort, "ARE_IDENTICAL_TO", trans_orig) # or "SHARE_A_LINE_SEGMENT_WITH"
if int(arcpy.GetCount_management(trans_presort)[0]) > 0:
    arcpy.DeleteFeatures_management(trans_presort) # if there are old transects in new transects, delete them
# Append relevant NAT transects to the new transects
arcpy.SelectLayerByLocation_management(trans_orig, "INTERSECT", barrierBoundary)
arcpy.Append_management(trans_orig, trans_presort)
pythonaddins.MessageBox("Now we'll stop so you can check that the transects are ready to be sorted either from the bottom up or top down. ", "Stop for manual processing.".format(trans_presort), 0)
exit()

# Sort and add unique ID
# Select first batch (48)
trans_sort_1, count1 = SpatialSort(trans_presort,trans_sort_1,"LR",reverse_order=False,sortfield="sort_ID")

if multi_batch_sort:
    # Select second batch
    trans_sort_2 = "transects_sort2"
    # azimuth >
    trans_sort_2, count2 = SpatialSort(trans_presort,trans_sort_2,"LR",reverse_order=True, startcount=count1)
    #arcpy.Append_management(trans_sort_2, trans_sort_1)
    # Select third batch
    trans_sort_3 = "transects_sort3"
    startcount=count1+count2
    trans_sort_3, count3 = SpatialSort(trans_presort,trans_sort_3,"LL",reverse_order=False, startcount=startcount)
    #arcpy.Append_management(trans_sort_3, trans_sort_1)
    # Select fourth batch
    trans_sort_4 = "transects_sort4"
    startcount=count1+count2+count3
    trans_sort_4, count4 = SpatialSort(trans_presort,trans_sort_4,"LL",reverse_order=False,startcount=startcount)
    arcpy.Append_management([trans_sort_2, trans_sort_3, trans_sort_4], trans_sort_1)

    arcpy.Sort_management(trans_sort_1, extendedTransects, [['SORT_ID','ASCENDING']])

ExtendLine(trans_sort_1,extendedTransects,extendlength,proj_code)
if len(arcpy.ListFields(extendedTransects,'OBJECTID*')) == 2:
    ReplaceFields(extendedTransects,{'OBJECTID':'OID@'})
"""
Previous code
"""
# To be completed after manual steps to fill gaps, making sure that the new transects have null values
# Split the set of transects to ensure that the sort from __ corner is accurate.
extTransects = PreprocessTransects(site,old_transects,sort_corner='LL')

# Experimental alternative:
# Create lines to use to sort new transects
arcpy.CreateFeatureclass_management(home,'sort_line1', "POLYLINE", spatial_reference=arcpy.SpatialReference(proj_code))
arcpy.CopyFeatures_management('sort_line1','{}\\sort_line2'.format(home))
sort_line_list = ['sort_line1','sort_line2']

SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield=transUIDfield,sort_corner='LL')

##### Merge beach metrics #####
arcpy.env.workspace = DHdir
outfile = r"{}\{}".format(home,dhPts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

arcpy.env.workspace = DLdir
outfile = r"{}\{}".format(home,dlPts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

arcpy.env.workspace = SLdir
outfile = r"{}\{}".format(home,ShorelinePts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

# DEM
elevGrid = ProcessDEM(site,year,old_dem,proj_code)

# Full shoreline
RasterToLandPerimeter(elevGrid,bndMHW,MHW)

# Inlet lines
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)
arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=arcpy.SpatialReference(proj_code))

"""
arcpy.Sort_management(ShorelinePts,ShorelinePts+'_sort',"lat")
with arcpy.da.UpdateCursor(ShorelinePts+'_sort',["OBJECTID","OID"]) as cursor:
    for row in cursor:
        cursor.updateRow([row[0], row[0]])
"""
#arcpy.PointsToLine_management(ShorelinePts, MHW_oceanside,Sort_Field="OID")
CreateShoreBetweenInlets(ShorelinePts,inletLines,shoreline,proj_code=26918)


NewBNDpoly(bndMHW,ShorelinePts,barrierBoundary,'25 METERS','25 METERS')
