
'''
Preprocessing for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov
Copied from TE_MASTER_v5 on 5/1/17

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options,
        uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
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


start = time.clock()

"""
Pre-processing
"""
# Check presence of default files in gdb
e_trans = SetInputFCname(home, 'extendedTrans', extendedTrans, system_ext=False)
t_trans = SetInputFCname(home, 'extTrans_tidy', extTrans_tidy, False)
i_name = SetInputFCname(home, 'inlets delineated (inletLines)', inletLines, False)
dhPts = SetInputFCname(home, 'dune crest points (dhPts)', dhPts)
dlPts = SetInputFCname(home, 'dune toe points (dlPts)', dlPts)
ShorelinePts = SetInputFCname(home, 'shoreline points (ShorelinePts)', ShorelinePts)
armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)
bb_name = SetInputFCname(home, 'barrier island polygon (barrierBoundary)',
                         barrierBoundary, False)
new_shore = SetInputFCname(home, 'shoreline between inlets', shoreline, False)
elevGrid_5m = SetInputFCname(home, 'DEM raster at 5m res (elevGrid_5m)',
                             elevGrid_5m, False)

#%% DUNE POINTS
# Replace fill values with Null
ReplaceValueInFC(dhPts, oldvalue=fill, newvalue=None, fields=["dhigh_z"])
ReplaceValueInFC(dlPts, oldvalue=fill, newvalue=None, fields=["dlow_z"])
ReplaceValueInFC(ShorelinePts, oldvalue=fill, newvalue=None, fields=["slope"])
# Populate ID with OID?

#%% INLETS
if not i_name:
    arcpy.CreateFeatureclass_management(home, inletLines, 'POLYLINE',
        spatial_reference=arcpy.SpatialReference(proj_code))
    print("{} created. Now we'll stop for you to manually create lines at each inlet.")
    exit()
else:
    inletLines = i_name

#%% ELEVATION
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)

#%% BOUNDARY POLYGON
if not bb_name:
    # Inlet lines must intersect MHW
    bndpoly = DEMtoFullShorelinePoly(elevGrid_5m, '{site}{year}'.format(**SiteYear_strings), MTL, MHW, inletLines, ShorelinePts)
    # Eliminate any remnant polygons on oceanside
    if pythonaddins.MessageBox('Ready to delete selected features from {}?'.format(bndpoly), '', 4) == 'Yes':
        arcpy.DeleteFeatures_management(bndpoly)
    else:
        print("Ok, redo.")
        exit()

    barrierBoundary = NewBNDpoly(bndpoly, ShorelinePts, barrierBoundary, '25 METERS', '50 METERS')
else:
    barrierBoundary = bb_name

if not arcpy.Exists(barrierBoundary):
    barrierBoundary = NewBNDpoly(bndpoly, ShorelinePts, barrierBoundary, '25 METERS', '50 METERS')

#%% SHORELINE
if not new_shore:
    shoreline = CreateShoreBetweenInlets(barrierBoundary, inletLines, shoreline, ShorelinePts, proj_code)
else:
    shoreline = new_shore

#%% TRANSECTS - extendedTrans
# Copy transects from archive directory
if not e_trans:
    print("Use TE_preprocess_transects.py to create the transects for processing.")
    exit()
"""
~~ start transect work
"""
# if transects already exist, but without correct field ID, use DuplicateField()
# DuplicateField(extendedTransects, 'TransOrder', tID_fld)
# arcpy.FeatureClassToFeatureClass_conversion(extendedTransects, trans_dir, os.path.basename(orig_extTrans))
# DeleteExtraFields(orig_extTrans, [tID_fld])
# arcpy.FeatureClassToFeatureClass_conversion(orig_extTrans, trans_dir, os.path.basename(orig_tidytrans))

# Create extendedTrans, LT transects with gaps filled and lines extended
trans_presort = 'trans_presort_temp'
LTextended = 'LTextended'
multi_sort = True # True indicates that the transects must be sorted in batches to preserve order
trans_sort_1 = 'trans_sort_temp'
t_trans = True

orig_trans = orig_trans+'_nad83'

arcpy.env.workspace = trans_dir
# Extend
ExtendLine(fc=orig_trans, new_fc=LTextended, distance=extendlength, proj_code=proj_code)
# 1. Copy only the geometry of transects to use as material for filling gaps
CopyAndWipeFC(LTextended, trans_presort, ['sort_ID'])
print("MANUALLY: use groups of existing transects in new FC '{}' to fill gaps. Avoid overlapping transects as much as possible".format(trans_presort))
exit()



PrepTransects_part2(trans_presort, LTextended, barrierBoundary)
if not multi_sort:
    SortTransectsFromSortLines(trans_presort, extendedTrans, sort_lines=[], sortfield=tID_fld, sort_corner='LL')
# Create lines to use to sort new transects
if multi_sort:
    sort_lines = 'sort_lines'
    arcpy.CreateFeatureclass_management(trans_dir, sort_lines, "POLYLINE", spatial_reference=arcpy.SpatialReference(proj_code))
    print("MANUALLY: Add features to sort_lines.")
    exit()
    SortTransectsFromSortLines(trans_presort, extendedTrans, sort_lines, sortfield=tID_fld)

if len(arcpy.ListFields(extendedTrans, 'OBJECTID*')) == 2:
    ReplaceFields(extendedTrans, {'OBJECTID': 'OID@'})

# TRANSECTS - tidyTrans
if not arcpy.Exists(orig_tidytrans):
    print("Manual work seems necessary to remove transect overlap")
    print("Select the boundary lines between groups of overlapping transects")
    # Select the boundary lines between groups of overlapping transects
    exit()
if not arcpy.Exists(orig_tidytrans):
    # Copy only the selected lines
    overlapTrans_lines = 'overlapTrans_lines_temp'
    arcpy.CopyFeatures_management(orig_extTrans, overlapTrans_lines)
    arcpy.SelectLayerByAttribute_management(orig_extTrans, "CLEAR_SELECTION")
    # Split transects at the lines of overlap.
    trans_x = 'overlap_points_temp'
    arcpy.Intersect_analysis([orig_extTrans, overlapTrans_lines], trans_x,
                             'ALL', output_type="POINT")
    arcpy.SplitLineAtPoint_management(orig_extTrans, trans_x, orig_tidytrans)
    print("MANUALLY: Select transect segments to be deleted. ")
    exit()

# alternative:
# overlap_geom = arcpy.CopyFeatures_management(orig_tidytrans, arcpy.Geometry())
# for line in overlap_geom:
#     for transect in arcpy.da.UpdateCursor(orig_tidytrans, ("SHAPE@", tID_fld)):
#         right, left = transect.cut(line) # If a geometry is not cut, left will be empty (None)

if not t_trans:
    arcpy.DeleteFeatures_management(orig_tidytrans)
    # arcpy.CopyFeatures_management(orig_tidytrans, extTrans_tidy_archive)
    extendedTrans = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt

#%% Create ID raster
arcpy.env.workspace = os.path.dirname(rst_transIDpath)
if not arcpy.Exists(os.path.basename(rst_transIDpath)):
    outEucAll = arcpy.sa.EucAllocation(orig_tidytrans, maximum_distance=50,
                                       cell_size=cell_size, source_field=tID_fld)
    outEucAll.save(os.path.basename(rst_transIDpath))
arcpy.env.workspace = home

#%% Shoreline-transect intersect points
arcpy.Intersect_analysis((shoreline, extendedTrans), intersect_shl2trans, output_type='POINT')
# shl2trans = 'ParkerRiver2014_SLpts2trans'
#FIXME: shljoin = JOIN closest feature in ShorelinePts to shl2trans
# right click on intersect layer, and
#fmap = 'sort_ID "sort_ID" true true false 2 Short 0 0 ,First,#,SHL2trans_temp,sort_ID,-1,-1; ID "ID" true true false 4 Float 0 0 ,First,#,\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\Delmarva\Assateague\2014\Assateague2014.gdb\Assateague2014_SLpts,ID,-1,-1'
# arcpy.SpatialJoin_analysis(shl2trans, os.path.join(home, ShorelinePts), 'join_temp','#','#', fmap, "CLOSEST", pt2trans_disttolerance) # create join_temp

"""
~~ end transect work
"""

print("Pre-processing completed.")

DeleteTempFiles()
