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

    PANDAS version 0.20.1 used for pickling

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

home = os.path.join(local_home, '{site}{year}.gdb'.format(**SiteYear_strings))
if sys.platform == 'win32':
    arcpy.env.workspace=home
out_dir = os.path.join(local_home, 'scratch')

#%% ####### Run ################################################################
start = time.clock()

"""
Pre-processing
"""
#%% extendedTransects
arcpy.env.workspace = trans_dir
if not arcpy.Exists(os.path.basename(orig_extTrans)):
    ExtendLine(fc=orig_trans, new_fc=os.path.basename(orig_extTrans), distance=extendlength, proj_code=proj_code)

# Transects do not encompass southern end of island. Need to add those and reset sort_ID
CopyAndWipeFC(orig_extTrans, 'extTrans_presort_temp', ['sort_ID'])

arcpy.Append_management('extTrans_presort_temp', orig_extTrans)
# When Append failed, I manually copied the features from orig_extTrans to extTrans_presort_temp
SortTransectsFromSortLines('extTrans_presort_temp', orig_extTrans+'_v2', sort_lines=[], sortfield=tID_fld, sort_corner='LL')
# Manually edited the first 7 sort_ID values

# Select the boundary lines between groups of overlapping transects
# Copy only the selected lines
overlapTrans_lines = 'overlapTrans_lines3_temp'
arcpy.CopyFeatures_management(orig_extTrans, overlapTrans_lines)
arcpy.SelectLayerByAttribute_management(orig_extTrans, "CLEAR_SELECTION")
# Split transects at the lines of overlap.
arcpy.env.workspace = trans_dir
overlapTrans_lines = 'overlap_line3_temp'
trans_x = 'overlap_points3_temp'
arcpy.Intersect_analysis([orig_extTrans, overlapTrans_lines], trans_x,
                         'ALL', output_type="POINT")
arcpy.SplitLineAtPoint_management(orig_extTrans, trans_x, orig_tidytrans+"_3")
# Manually (in Edit session) delete transect tails
overlapTrans_lines = 'overlap_line4_temp'
trans_x = 'overlap_points4_temp'
arcpy.Intersect_analysis([orig_extTrans, overlapTrans_lines], trans_x,
                         'ALL', output_type="POINT")
arcpy.SplitLineAtPoint_management(orig_extTrans, trans_x, orig_tidytrans+"_4")
# Manually (in Edit session) delete transect tails

DeleteTempFiles()
arcpy.FeatureClassToFeatureClass_conversion(orig_extTrans, home, extendedTransects)

"""
SPATIAL: transects
"""
#%% Create trans_df
trans_df = FCtoDF(extendedTransects, id_fld=tID_fld, extra_fields=extra_fields)
trans_df.drop(extra_fields, axis=1, inplace=True, errors='ignore')
trans_df.to_pickle(os.path.join(out_dir, 'trans_df.pkl'))
if sys.platform == 'darwin':
    trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df.pkl'))

#%% Add XY and Z/slope from DH, DL, SL points within 10m of transects
sl2trans_df = add_shorelinePts2Trans(extendedTransects, ShorelinePts, shoreline, tID_fld=tID_fld, proximity=pt2trans_disttolerance)
sl2trans_df.to_pickle(os.path.join(out_dir, 'sl2trans.pkl'))

dh2trans_df = find_ClosestPt2Trans_snap(extendedTransects, dhPts, trans_df, 'DH', tID_fld, proximity=pt2trans_disttolerance)
dh2trans_df.to_pickle(os.path.join(out_dir, 'dh2trans.pkl'))

dl2trans_df = find_ClosestPt2Trans_snap(extendedTransects, dlPts, trans_df, 'DL', tID_fld, proximity=pt2trans_disttolerance)
dl2trans_df.to_pickle(os.path.join(out_dir, 'dl2trans.pkl'))

trans_df = ArmorLineToTrans_PD(extendedTransects, trans_df, armorLines, tID_fld, proj_code, elevGrid_5m)

trans_df = join_columns_id_check(trans_df, sl2trans_df, tID_fld)

if sys.platform == 'darwin':
    sl2trans_df = pd.read_pickle(os.path.join(out_dir, 'sl2trans.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df_SL.pkl'))
    dh2trans_df = pd.read_pickle(os.path.join(out_dir, 'dh2trans.pkl'))
    dl2trans_df = pd.read_pickle(os.path.join(out_dir, 'dl2trans.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df_beachmetrics.pkl'))

trans_df.loc[133]
trans_df = join_columns_id_check(trans_df, dh2trans_df, tID_fld)
trans_df = join_columns_id_check(trans_df, dl2trans_df, tID_fld)
trans_df.to_pickle(os.path.join(out_dir, 'trans_df_beachmetrics.pkl'))


DFtoFC(dl2trans_df, 'ptSnap2trans_DL', spatial_ref=utmSR, id_fld=tID_fld, xy=["DL_snapX", "DL_snapY"], keep_fields=['DL_z'])
DFtoFC(dh2trans_df, 'ptSnap2trans_DH', spatial_ref=utmSR, id_fld=tID_fld, xy=["DH_snapX", "DH_snapY"], keep_fields=['DH_z'])
sl2trans_df = pd.read_pickle(os.path.join(out_dir, 'sl2trans.pkl'))
DFtoFC(sl2trans_df, 'pts2trans_SL', spatial_ref=utmSR, id_fld=tID_fld, xy=["SL_x", "SL_y"], keep_fields=['Bslope'])

# if os.path.exists(os.path.join(out_dir, 'pts2trans_df.pkl')):
#     pts2trans_df = pd.read_pickle(os.path.join(out_dir, 'pts2trans_df.pkl'))
# else:
#     pts2trans_df = add_Pts2Trans(extendedTransects, dlPts, dhPts, ShorelinePts, shoreline, tID_fld=tID_fld, proximity=pt2trans_disttolerance, verbose=True)
#     pts2trans_df.to_pickle(os.path.join(out_dir, 'pts2trans_df.pkl'))
# trans_df = join_columns(trans_df, pts2trans_df)

#%% Calculate distances from shore to dunes, etc.
# trans_df = calc_BeachWidth(extendedTransects, trans_df, maxDH, tID_fld, MHW)
trans_df, dl2trans, dh2trans, arm2trans = calc_BeachWidth_fill(extendedTransects, trans_df, maxDH, tID_fld, MHW, fill)
#%% failing on join in adjust2mhw() in calc_BeachWidth_fill


# trans_df.to_pickle(os.path.join(out_dir, 'trans_df_bw.pkl'))
# trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df_bw.pkl'))

#%% Don't require trans_df
# Dist2Inlet: Calc dist from inlets SPATIAL
# dist_df = measure_Dist2Inlet(shoreline, extendedTransects, tID_fld)
dist_df = measure_Dist2Inlet(shoreline, extendedTransects, inletLines, tID_fld)
dist_df.to_pickle(os.path.join(out_dir, 'dist2inlet_df.pkl'))
dist_df = pd.read_pickle(os.path.join(out_dir, 'dist2inlet_df.pkl'))
trans_df.loc[[133, 270]]
# trans_df = join_columns(trans_df, dist_df, tID_fld)
trans_df = join_columns_id_check(trans_df, dist_df, tID_fld, fill=fill)
trans_df.loc[[133, 270]]
trans_df.to_pickle(os.path.join(out_dir, 'trans_df_dist2inlet.pkl'))

# Clip transects, get barrier widths *SPATIAL*
widths_df = calc_IslandWidths(extendedTransects, barrierBoundary, tID_fld=tID_fld)
widths_df = pd.read_pickle(os.path.join(out_dir, 'widths_df.pkl'))
# trans_df = join_columns(trans_df, widths_df, tID_fld)
trans_df = join_columns_id_check(trans_df, widths_df, tID_fld, fill=fill)
trans_df.loc[[133, 270]]
# trans_fc = JoinDFtoFC(trans_df, extendedTransects, tID_fld, out_fc=extTrans_fill)
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))

trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))

#%%
"""
5m Points
"""
#%%
if os.path.exists(os.path.join(out_dir, transPts_null+'.pkl')):
    pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
if not arcpy.Exists(transPts_presort):
    # pts_df, transPts_presort = TransectsToPointsDF(extTrans_tidy, barrierBoundary, fc_out=transPts_presort) # 1 hr 10 minutes for Assateague
    #%% Run instead of TransectsToPointsDF() because that caused problems:
    in_trans = extTrans_tidy
    fc_out=transPts_presort
    step=5
    out_tidyclipped=r'\\Mac\Home\Documents\ArcGIS\Default.gdb\Monomoy2014_tidytrans_clipped'
    arcpy.Clip_analysis(in_trans, barrierBoundary, out_tidyclipped) # saved to Default
    df = pd.DataFrame(columns=[tID_fld, 'seg_x', 'seg_y'])
    with arcpy.da.SearchCursor(out_tidyclipped, ("SHAPE@", tID_fld)) as cursor:
        for row in cursor:
            ID = row[1]
            line = row[0]
            # Get points in 5m increments along transect and save to df
            for i in range(0, int(line.length), step):
                pt = line.positionAlongLine(i)[0]
                df = df.append({tID_fld:ID, 'seg_x':pt.X, 'seg_y':pt.Y}, ignore_index=True)
    df.to_pickle(os.path.join(out_dir, 'pts_df.pkl'))
    if len(fc_out) > 1:
        print('Converting new dataframe to feature class...')
        # fc = '{}_{}mPts_unsorted'.format(in_trans, step)
        DFtoFC(df, fc_out, id_fld=tID_fld, spatial_ref = utmSR) # IOError
        # duration = print_duration(start)
        pts_df, transPts_presort = df, fc_out

    #%% Run instead of DFtoFC() because that caused problems:
    df = pd.read_pickle(os.path.join(out_dir, 'pts_df.pkl'))
    fc = transPts_presort
    id_fld = tID_fld
    spatial_ref = utmSR
    keep_fields = []
    xy=["seg_x", "seg_y"]
    if df.index.name in df.columns:
        df.index.name = 'index'
    # Convert DF to array
    keep_fields += xy + [id_fld]
    # Remove any rows with X or Y == None
    xfld = xy[0]
    df = df[~df[xfld].isnull()]
    df = df[df[xfld]!=fill]
    # Remove 'object' type columns, all columns not in keep_fields, convert to floats, and fill Nulls.
    try:
        arr = (df.select_dtypes(exclude=['object'])
                 .drop(df.columns.drop(keep_fields, errors='ignore'), errors='ignore', axis=1)
                 .astype('f8').fillna(fill).to_records())
    except ValueError:
        df.index.name = 'index'
        arr = (df.select_dtypes(exclude=['object'])
             .drop(df.columns.drop(keep_fields, errors='ignore'), errors='ignore', axis=1)
             .astype('f8').fillna(fill).to_records())
        print('Encountered ValueError while converting dataframe to array so set index name to "index" before running.' )
    # Convert array to FC
    fc = os.path.join(arcpy.env.scratchGDB, os.path.basename(fc)) # set fc path
    arcpy.Delete_management(fc) # delete if already exists
    arcpy.da.NumPyArrayToFeatureClass(arr, fc, xy, spatial_ref)

if not 'ptZ' in pts_df.columns:
    pts_df = pd.read_pickle(os.path.join(out_dir, 'pts_df.pkl'))
    transPts_presort = os.path.join(arcpy.env.scratchGDB, transPts_presort)
    slopeGrid = '{site}{year}_slope5m'.format(**SiteYear_strings)
    # Extract elevation and slope at points
    if not arcpy.Exists(elevGrid_5m):
        ProcessDEM(elevGrid, elevGrid_5m, utmSR)
    if not arcpy.Exists(slopeGrid):
        arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
    arcpy.sa.ExtractMultiValuesToPoints(transPts_presort, [[elevGrid_5m, 'ptZ'], [slopeGrid, 'ptSlp']]) # 9 min for ParkerRiver
    # Convert points to DataFrames
    pts_df = FCtoDF(transPts_presort, xy=True, dffields=[tID_fld, 'ptZ', 'ptSlp'])
    pts_df.to_pickle(os.path.join(out_dir, 'pts_df_elev_slope.pkl'))

#%% pts_df should not have Null/fills and trans_df should not have Null/fills in sort_ID
if pts_df['SHAPE@X'].isnull().values.any():
    raise ValueError('Field "SHAPE@X" is missing values.'.format(tID_fld))

#%% PANDAS only. Most recently commpleted on Windows because Atom and Arc are using different python versions and Arc can't read Atom's pickle files.
if sys.platform == 'darwin':
    pts_df = pd.read_pickle(os.path.join(out_dir, 'pts_df_elev_slope.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))

# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm, sort points
pts_df = join_columns_orig(pts_df, trans_df, tID_fld) # resulted in 4 additional rows

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
try:
    pts_df.to_excel(os.path.join(out_dir, transPts_fill +'_pd.xlsx'), na_rep=fill, index=False)
except:
    print("No Excel file created. You'll have to do it yourself from the CSV.")

#%% Create ID raster
arcpy.env.workspace = os.path.join(arcpy.env.scratchWorkspace, '{site}{year}.gdb'.format(**SiteYear_strings))
orig_tidytrans = os.path.join(arcpy.env.scratchWorkspace, '{site}{year}.gdb'.format(**SiteYear_strings), 'Monomoy_tidyTrans')
rst_transIDpath = os.path.join(arcpy.env.scratchWorkspace,  '{site}{year}.gdb'.format(**SiteYear_strings), "{site}_rstTransID".format(**SiteYear_strings))
rst_bwgrid_path = os.path.join(arcpy.env.workspace, "{code}".format(**SiteYear_strings))
if not arcpy.Exists(os.path.basename(rst_transIDpath)):
    outEucAll = arcpy.sa.EucAllocation(orig_tidytrans, maximum_distance=50,
                                       cell_size=cell_size, source_field=tID_fld)
    outEucAll.save(os.path.basename(rst_transIDpath))
arcpy.env.workspace = home

#%% Create Beach Width raster by join DF to ID raster
bw_rst="{code}_ubw".format(**SiteYear_strings)
rst_transID = "{site}_rstTransID".format(**SiteYear_strings)
JoinDFtoRaster(trans_df, rst_transID, bw_rst, fill, tID_fld, 'uBW')
trans_fc = JoinDFtoFC(trans_df, extendedTransects, tID_fld, out_fc=extTrans_fill)

# Convert pts_df to FC, both pts and trans (pts_fc, trans_fc)
pts_fc = DFtoFC_large(pts_df, outFC_pts=transPts_fill, spatial_ref=utmSR, df_id=pID_fld, xy=["seg_x", "seg_y"])

# Save final SHP and FCs with null values
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, out_dir, transPts_shp+'.shp')
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
shutil.copy(os.path.join(script_path, 'TE_master_2.py'), os.path.join(code_dir, 'TE_master_2.py'))
shutil.copy(os.path.join(script_path, 'TE_config.py'), os.path.join(code_dir, 'TE_config.py'))
shutil.copy(os.path.join(script_path, 'TE_functions.py'), os.path.join(code_dir, 'TE_functions.py'))
shutil.copy(os.path.join(script_path, 'TE_functions_arcpy.py'), os.path.join(code_dir, 'TE_functions_arcpy.py'))
