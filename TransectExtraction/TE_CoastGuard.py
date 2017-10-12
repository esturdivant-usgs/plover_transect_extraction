# -*- coding: utf-8 -*-
'''
Deep dive Transect Extraction
Requires: python 3, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options,
        uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 19N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
import os
import sys
import time
import shutil
import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt
# path to TransectExtraction module
if sys.platform == 'win32':
    script_path = r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction"
    sys.path.append(script_path) # path to TransectExtraction module
    import arcpy
    # import pythonaddins
    from TE_functions_arcpy import *
if sys.platform == 'darwin':
    script_path = '/Users/esturdivant/GitHub/plover_transect_extraction/TransectExtraction'
    sys.path.append(script_path)
from TE_config import *
from TE_functions import *

#%% ####### Run ###############################################################
start = time.clock()
"""
Pre-processing
"""
#%% Beach metrics
# Check the points for irregularities
ReplaceValueInFC(dhPts, oldvalue=fill, newvalue=None, fields=["dhigh_z"])
ReplaceValueInFC(dlPts, oldvalue=fill, newvalue=None, fields=["dlow_z"])
ReplaceValueInFC(ShorelinePts, oldvalue=fill, newvalue=None, fields=["slope"])


#%% Shoreline polygon
bndpoly = DEMtoFullShorelinePoly(elevGrid_5m, '{site}{year}'.format(**SiteYear_strings), MTL, MHW, inletLines, ShorelinePts)
# Failed because missing inletLines
# I created inletLines at Nauset inlet. None on either side. Not sure how this will go.
CombineShorelinePolygons(bndMTL, bndMHW, inletLines, ShorelinePts, bndpoly)
# Failed because missing ShorelinePts
# Convert slpts shapefile to gdb
union = 'union_temp'
split_temp = 'split_temp'
union_2 = 'union_2_temp'
arcpy.SelectLayerByLocation_management(split_temp, "INTERSECT", ShorelinePts, '#', "NEW_SELECTION")
arcpy.Erase_analysis(union, split_temp, union_2)
arcpy.Dissolve_management(union_2, bndpoly, multi_part='SINGLE_PART')

# Eliminate any remnant polygons on oceanside
# Select features that shouldn't be included. Then delete them.
arcpy.DeleteFeatures_management(bndpoly)

barrierBoundary = NewBNDpoly(bndpoly, ShorelinePts, barrierBoundary, '25 METERS', '50 METERS')

#%% ShoreBetweenInlets
shoreline = CreateShoreBetweenInlets(barrierBoundary, inletLines, shoreline, ShorelinePts, proj_code)

#%% Transects
# Create extendedTrans, LT transects with gaps filled and lines extended
trans_presort = 'trans_presort_temp'
LTextended = 'LTextended'
trans_sort_1 = 'trans_sort_temp'
extTrans_sort_ext = 'extTrans_temp'

arcpy.env.workspace = trans_dir
# 1.  Extend and Copy only the geometry of transects to use as material for filling gaps
ExtendLine(fc=orig_trans, new_fc=LTextended, distance=extendlength, proj_code=proj_code)
CopyAndWipeFC(LTextended, trans_presort, ['sort_ID'])
# Manually fill gaps in transects

# 2. automatically sort.
PrepTransects_part2(trans_presort, LTextended, barrierBoundary)
SortTransectsFromSortLines(trans_presort, extendedTrans, sort_lines=[], sortfield=tID_fld, sort_corner='LR')
# Manually edit values at choke point.

arcpy.FeatureClassToFeatureClass_conversion(extendedTrans, orig_tidytrans)
arcpy.env.workspace = home

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

#%% Create trans_df
trans_df = FCtoDF(extendedTransects, id_fld=tID_fld, extra_fields=extra_fields)
trans_df.drop(extra_fields, axis=1, inplace=True, errors='ignore')
trans_df.to_pickle(os.path.join(scratch_dir, 'trans_df.pkl'))
if sys.platform == 'darwin':
    trans_df = pd.read_pickle(os.path.join(scratch_dir, 'trans_df.pkl'))

#%% Add XY and Z/slope from DH, DL, SL points within 10m of transects
sl2trans_df = add_shorelinePts2Trans(extendedTransects, ShorelinePts, shoreline, tID_fld, proximity=pt2trans_disttolerance)
sl2trans_df.to_pickle(os.path.join(scratch_dir, 'sl2trans.pkl'))
DFtoFC(sl2trans_df, 'pts2trans_SL', spatial_ref=utmSR, id_fld=tID_fld, xy=["SL_x", "SL_y"], keep_fields=['Bslope'])

dh2trans_df = find_ClosestPt2Trans_snap(extendedTransects, dhPts, trans_df, 'DH', tID_fld, proximity=pt2trans_disttolerance)
dh2trans_df.to_pickle(os.path.join(scratch_dir, 'dh2trans.pkl'))
DFtoFC(dh2trans_df, 'ptSnap2trans_DH', spatial_ref=utmSR, id_fld=tID_fld, xy=["DH_snapX", "DH_snapY"], keep_fields=['DH_z'])

dl2trans_df = find_ClosestPt2Trans_snap(extendedTransects, dlPts, trans_df, 'DL', tID_fld, proximity=pt2trans_disttolerance)
dl2trans_df.to_pickle(os.path.join(scratch_dir, 'dl2trans.pkl'))
DFtoFC(dl2trans_df, 'ptSnap2trans_DL', spatial_ref=utmSR, id_fld=tID_fld, xy=["DL_snapX", "DL_snapY"], keep_fields=['DL_z'])

trans_df = ArmorLineToTrans_PD(extendedTransects, trans_df, armorLines, tID_fld, proj_code, elevGrid_5m)

trans_df = join_columns_id_check(trans_df, sl2trans_df, tID_fld)
trans_df = join_columns_id_check(trans_df, dh2trans_df, tID_fld)
trans_df = join_columns_id_check(trans_df, dl2trans_df, tID_fld)
trans_df.to_pickle(os.path.join(scratch_dir, 'trans_df_beachmetrics.pkl'))

if sys.platform == 'darwin':
    sl2trans_df = pd.read_pickle(os.path.join(scratch_dir, 'sl2trans.pkl'))
    # trans_df = pd.read_pickle(os.path.join(scratch_dir, 'trans_df_SL.pkl'))
    dh2trans_df = pd.read_pickle(os.path.join(scratch_dir, 'dh2trans.pkl'))
    dl2trans_df = pd.read_pickle(os.path.join(scratch_dir, 'dl2trans.pkl'))
    trans_df = pd.read_pickle(os.path.join(scratch_dir, 'trans_df_beachmetrics.pkl'))


#%% Calculate distances from shore to dunes, etc.
trans_df, dl2trans, dh2trans, arm2trans = calc_BeachWidth_fill(extendedTransects, trans_df, maxDH, tID_fld, MHW, fill)

#%% Don't require trans_df
# Dist2Inlet: Calc dist from inlets SPATIAL
dist_df = measure_Dist2Inlet(shoreline, extendedTransects, inletLines, tID_fld)
# dist_df.to_pickle(os.path.join(out_dir, 'dist2inlet_df.pkl'))
# dist_df = pd.read_pickle(os.path.join(out_dir, 'dist2inlet_df.pkl'))
# trans_df.loc[[133, 270]]
# trans_df = join_columns(trans_df, dist_df, tID_fld)
trans_df = join_columns_id_check(trans_df, dist_df, tID_fld, fill=fill)
# trans_df.loc[[133, 270]]
trans_df.to_pickle(os.path.join(out_dir, 'trans_df_dist2inlet.pkl'))

# Clip transects, get barrier widths *SPATIAL*
widths_df = calc_IslandWidths(extendedTransects, barrierBoundary, tID_fld=tID_fld)
# widths_df.to_pickle(os.path.join(out_dir, 'widths_df.pkl'))
# widths_df = pd.read_pickle(os.path.join(out_dir, 'widths_df.pkl'))
# trans_df = join_columns(trans_df, widths_df, tID_fld)
trans_df = join_columns_id_check(trans_df, widths_df, tID_fld, fill=fill)
# trans_df.loc[[133, 270]]
# trans_fc = JoinDFtoFC(trans_df, extendedTransects, tID_fld, out_fc=extTrans_fill)
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))

# trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))

#%%
"""
5m Points
"""
#%%
if os.path.exists(os.path.join(scratch_dir, transPts_null+'.pkl')):
    pts_df = pd.read_pickle(os.path.join(scratch_dir,transPts_null+'.pkl'))
    trans_df = pd.read_pickle(os.path.join(scratch_dir, extTrans_null+'_prePts.pkl'))
if not arcpy.Exists(transPts_presort):
    pts_df, transPts_presort = TransectsToPointsDF(extTrans_tidy, barrierBoundary, fc_out=transPts_presort) # 1 hr 10 minutes for Assateague

if not 'ptZ' in pts_df.columns:
    # Extract elevation and slope at points
    if not arcpy.Exists(elevGrid_5m):
        ProcessDEM(elevGrid, elevGrid_5m, utmSR)
    if not arcpy.Exists(slopeGrid):
        arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
    arcpy.sa.ExtractMultiValuesToPoints(os.path.join(scratch_dir, transPts_presort), [[elevGrid_5m, 'ptZ'], [slopeGrid, 'ptSlp']]) # 9 min for ParkerRiver
    pts_df = FCtoDF(transPts_presort, xy=True, dffields=[tID_fld,'ptZ', 'ptSlp'])
    pts_df.to_pickle(os.path.join(scratch_dir, 'pts_df_elev_slope.pkl'))

#%%
pts_df = pd.read_pickle(os.path.join(scratch_dir, 'pts_df_elev_slope.pkl'))
trans_df = pd.read_pickle(os.path.join(scratch_dir, extTrans_null+'_prePts.pkl'))

# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm, sort points
pts_df = join_columns(pts_df, trans_df, tID_fld)
pts_df = prep_points(pts_df, tID_fld, pID_fld, MHW, fill)
# Aggregate ptZmhw to max and mean and join to transPts and extendedTransects
pts_df, zmhw = aggregate_z(pts_df, MHW, tID_fld, 'ptZ', fill)
trans_df = join_columns(trans_df, zmhw) # join new fields to transects
pts_df = join_columns(pts_df, trans_df, tID_fld) # Join transect values to pts

# Housecleaning
trans_df.drop(extra_fields, axis=1, inplace=True, errors='ignore') # Drop extra fields
pts_df.drop(extra_fields, axis=1, inplace=True, errors='ignore') # Drop extra fields
# pts_df.loc[pts_df.sort_ID == 615, :].iloc[0,:]

#%% Save dataframes to open elsewhere or later
trans_df.to_pickle(os.path.join(scratch_dir, extTrans_null+'.pkl'))
pts_df.to_pickle(os.path.join(scratch_dir, transPts_null+'.pkl'))
if sys.platform == 'darwin':
    pts_df = pd.read_pickle(os.path.join(scratch_dir,transPts_null+'.pkl'))
    trans_df = pd.read_pickle(os.path.join(scratch_dir, extTrans_null+'.pkl'))

#%%
"""
Outputs
"""
# Save final pts with fill values as CSV
if not pID_fld in pts_df.columns:
    pts_df.reset_index(drop=False, inplace=True)
csv_fname = os.path.join(scratch_dir, transPts_fill +'_pd.csv')
pts_df.to_csv(os.path.join(scratch_dir, transPts_fill +'_pd.csv'), na_rep=fill, index=False)
print("OUTPUT: {}".format(csv_fname))
try:
    xls_fname = os.path.join(scratch_dir, transPts_fill +'_pd.xlsx')
    pts_df.to_excel(xls_fname, na_rep=fill, index=False)
    print("OUTPUT: {}".format(xls_fname))
except:
    print("No Excel file created. You'll have to do it yourself from the CSV.")

#%% Create ID raster
if not arcpy.Exists(os.path.basename(rst_transIDpath)):
    outEucAll = arcpy.sa.EucAllocation(orig_tidytrans, maximum_distance=50,
                                       cell_size=cell_size, source_field=tID_fld)
    outEucAll.save(os.path.basename(rst_transIDpath))

#%% Create Beach Width raster by joining DF to ID raster
out_rst = JoinDFtoRaster(trans_df, rst_transID, bw_rst, fill, tID_fld, 'uBW')
trans_fc = JoinDFtoFC(trans_df, extendedTransects, tID_fld, out_fc=extTrans_fill)
print("OUTPUT: {}".format(trans_fc))

# Convert pts_df to FC, both pts and trans (pts_fc, trans_fc)
pts_fc = DFtoFC_large(pts_df, outFC_pts=transPts_fill, spatial_ref=utmSR, df_id=pID_fld, xy=["seg_x", "seg_y"])

# Save final SHP and FCs with null values
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, scratch_dir, transPts_shp+'.shp')
CopyFCandReplaceValues(pts_fc, fill, None, out_fc=transPts_null, out_dir=home)
# arcpy.FeatureClassToFeatureClass_conversion(pts_fc, home, transPts_null)
# ReplaceValueInFC(transPts_null, fill, None)
CopyFCandReplaceValues(trans_fc, fill, None, out_fc=extTrans_null, out_dir=home)
# arcpy.FeatureClassToFeatureClass_conversion(trans_fc, home, extTrans_null)
# ReplaceValueInFC(extTrans_null, fill, None)

# Export the files used to run the process to code file in home dir
# os.makedirs(code_dir, exist_ok=True)
try:
    os.makedirs(code_dir)
except OSError:
    if not os.path.isdir(code_dir):
        raise
shutil.copy(os.path.join(script_path, 'TE_CoastGuard.py'), os.path.join(code_dir, 'TE_CoastGuard.py'))
shutil.copy(os.path.join(script_path, 'TE_config.py'), os.path.join(code_dir, 'TE_config.py'))
shutil.copy(os.path.join(script_path, 'TE_functions.py'), os.path.join(code_dir, 'TE_functions.py'))
shutil.copy(os.path.join(script_path, 'TE_functions_arcpy.py'), os.path.join(code_dir, 'TE_functions_arcpy.py'))
