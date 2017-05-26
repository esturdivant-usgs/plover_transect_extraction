# -*- coding: utf-8 -*-
'''
Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com

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

#%% ####### Run ################################################################
start = time.clock()

"""
SPATIAL: transects
"""
#%% extendedTransects
# DeleteTempFiles()
if not arcpy.Exists(shoreline):
    if not arcpy.Exists(barrierBoundary):
        barrierBoundary = NewBNDpoly(bndpoly, ShorelinePts, barrierBoundary, '25 METERS', '50 METERS')
    CreateShoreBetweenInlets(barrierBoundary, inletLines, shoreline, ShorelinePts, proj_code)
if not arcpy.Exists(extendedTransects):
    arcpy.FeatureClassToFeatureClass_conversion(orig_extTrans, home, extendedTransects)

# 1: Add XYZ from DH, DL points within 10m of transects
# Convert transects and points to DataFrames
# PointMetricsToTransects(extendedTransects, dhPts, "dh2trans", 'DH', tID_fld, tolerance=pt2trans_disttolerance)
# PointMetricsToTransects(extendedTransects, dlPts, "dl2trans", 'DL', tID_fld, tolerance=pt2trans_disttolerance)

trans_df = FCtoDF(extendedTransects, id_fld=tID_fld, extra_fields=extra_fields)

dh2trans_df = find_ClosestPt2Trans(extendedTransects, dhPts, 'DH', tID_fld, snaptoline_on=False, proximity=pt2trans_disttolerance)
dl2trans_df = find_ClosestPt2Trans(extendedTransects, dlPts, 'DL', tID_fld, snaptoline_on=False, proximity=pt2trans_disttolerance) # duration: 13:24 sec for 411 transects
# dh2trans_df.to_pickle(os.path.join(out_dir, 'dh2trans_df.pkl'))
# dl2trans_df.to_pickle(os.path.join(out_dir, 'dl2trans_df.pkl'))
trans_df = join_columns(trans_df, dh2trans_df)
trans_df = join_columns(trans_df, dl2trans_df)

# 2: Add XYZ Arm points and XYslope from SL points within 10m of transects
sl2trans_df = add_shorelinePts2Trans(extendedTransects, ShorelinePts, shoreline, tID_fld=tID_fld, proximity=pt2trans_disttolerance)
trans_df = join_columns(trans_df, sl2trans_df)

trans_df = ArmorLineToTrans_PD(extendedTransects, trans_df, armorLines, tID_fld, proj_code, elevGrid_5m)

# 3: Dist2Inlet: Calc dist from inlets SPATIAL
dist_df = measure_Dist2Inlet(shoreline, extendedTransects, tID_fld)
trans_df = join_columns(trans_df, dist_df)

# 4: Clip transects, get barrier widths *SPATIAL*
widths_df = calc_IslandWidths(extendedTransects, barrierBoundary, tID_fld=tID_fld)
trans_df = join_columns(trans_df, widths_df)

# Calculate distances from shore to dunes, etc.
trans_df = calc_BeachWidth(extendedTransects, trans_df, maxDH, tID_fld, MHW)

# trans_df.to_pickle(os.path.join(out_dir, 'trans_df.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df.pkl'))

#%%
"""
5m Points
"""
#%% pts_df
# 5: Split transects into points *SPATIAL*
# SplitTransectsToPoints(orig_tidytrans, transPts_presort, barrierBoundary, temp_gdb)
pts_df, transPts_presort = TransectsToPointsDF(extTrans_tidy, barrierBoundary, out_tidyclipped=tidy_clipped, fc_out=True) # 12 minutes for ParkerRiver

#%%
# 6: Extract elev and slope at points *SPATIAL*
# Create slope grid if doesn't already exist
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)
if not arcpy.Exists(slopeGrid):
    arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
# Extract elevation and slope at points
arcpy.sa.ExtractMultiValuesToPoints(transPts_presort, [[elevGrid_5m, 'ptZ'],
                                    [slopeGrid, 'ptSlp']]) # 9 min for ParkerRiver
# Convert points to DataFrames
pts_df = FCtoDF(transPts_presort, xy=True, dffields=[tID_fld,'ptZ', 'ptSlp'])

#%%
# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
pts_df = join_columns(pts_df, trans_df, tID_fld)
pts_df = prep_points(pts_df, tID_fld, pID_fld, MHW)

# Aggregate ptZmhw to max and mean and join to transPts and extendedTransects
pts_df, zmhw = aggregate_z(pts_df, MHW, tID_fld, 'ptZ')
trans_df = join_columns(trans_df, zmhw) # join new fields to transects
pts_df = join_columns(pts_df, trans_df, tID_fld) # Join transect values to pts

# Drop extra fields
trans_df.drop(extra_fields, axis=1, inplace=True, errors='ignore')
pts_df.drop(extra_fields, axis=1, inplace=True, errors='ignore')

#%% Save dataframes to open elsewhere or later
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
pts_df.to_pickle(os.path.join(out_dir, transPts_null+'.pkl'))
if sys.platform == 'darwin':
    pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))

#%%
"""
Outputs
"""
# Save final pts with fill values as CSV
if not pID_fld in pts_df.columns:
    pts_df.reset_index(drop=False, inplace=True)
pts_df.to_csv(os.path.join(out_dir, transPts_fill +'_pd.csv'), na_rep=fill, index=False)
print("The table ({}.csv) was exported as a CSV to {}. Now:\n\n"\
      "1. Open the CSV in Excel and Save as... a .xlsx file. \n"\
      "2. Open the XLS in Matlab to check for errors! ".format(transPts_fill, out_dir))

# Convert pts_df to FC, both pts and trans (pts_fc, trans_fc)
# ** Takes a while **
transPts_fill = transPts_fill+'_fromDF'
#FIXME: still having problems
pts_fc, trans_fc = DFtoFC_large(pts_df, outFC_pts=transPts_fill, trans_df=trans_df,
                        trans_fc=extendedTransects, spatial_ref=utmSR, pt_flds=pt_flds, group_flds=trans_flds)

#%% Join DF to ID raster
bw_rst = JoinDFtoRaster_setvalue(bws_trans, rst_transIDpath, rst_bwgrid_path, fill=fill, id_fld=tID_fld, val_fld='uBW')
# bw_rst = JoinDFtoRaster_setvalue(trans_df, rst_transIDpath, rst_bwgrid_path, fill=fill, id_fld=tID_fld)


# Save final SHP and FCs with null values
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, out_dir, transPts_shp+'.shp')
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, home, transPts_null)
ReplaceValueInFC(transPts_null, fill, None)
arcpy.FeatureClassToFeatureClass_conversion(trans_fc, home, extTrans_null)
ReplaceValueInFC(extTrans_null, fill, None)

# Export the files used to run the process to code file in home dir
# os.makedirs(code_dir, exist_ok=True)
try:
    os.makedirs(code_dir)
except OSError:
    if not os.path.isdir(code_dir):
        raise
shutil.copy(os.path.join(script_path, 'TE_master_rework.py'), os.path.join(code_dir, 'TE_master_rework.py'))
shutil.copy(os.path.join(script_path, 'TE_config.py'), os.path.join(code_dir, 'TE_config.py'))
shutil.copy(os.path.join(script_path, 'TE_functions.py'), os.path.join(code_dir, 'TE_functions.py'))
shutil.copy(os.path.join(script_path, 'TE_functions_arcpy.py'), os.path.join(code_dir, 'TE_functions_arcpy.py'))
