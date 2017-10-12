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
trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df.pkl'))

#%% Calculate distances from shore to dunes, etc.
trans_df, dl2trans, dh2trans, arm2trans = calc_BeachWidth_fill(extendedTransects, trans_df, maxDH, tID_fld, MHW, fill)

# Checked that FC extTrans_null has same values as trans_df_bw

trans_df.to_pickle(os.path.join(out_dir, 'trans_df_bw.pkl'))
if sys.platform == 'darwin':
    trans_df_bw = pd.read_pickle(os.path.join(out_dir, 'trans_df_bw.pkl'))
    trans_df_eT = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))

# Check that df extTrans_null has same values as trans_df_bw
trans_df_bw.tail()
trans_df_eT.tail()

# extTrans_null.pkl seems to be up-to-date with extTrans_null FC

# Check that uBW in pts_df is up-to-date with extTrans_null
if sys.platform == 'darwin':
    trans_df_eT = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
    pts_df = pd.read_pickle(os.path.join(out_dir, 'pts_df_elev_slope.pkl'))

# Check that transect-average values in pts_df are exact match trans_df
trans_df_eT.uBW.equals(pts_df.groupby(tID_fld)['uBW'].first())

#%%
"""
5m Points
"""
#%%
if os.path.exists(os.path.join(out_dir, transPts_null+'.pkl')):
    pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
    trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
if not arcpy.Exists(transPts_presort):
    pts_df, transPts_presort = TransectsToPointsDF(extTrans_tidy, barrierBoundary, fc_out=transPts_presort) # 1 hr 10 minutes for Assateague
if not 'ptZ' in pts_df.columns:
    if os.path.exists(os.path.join(out_dir, 'pts_df_elev_slope.pkl')):
        pts_df = pd.read_pickle(os.path.join(out_dir, 'pts_df_elev_slope.pkl'))
    else:
        # Extract elevation and slope at points
        if not arcpy.Exists(elevGrid_5m):
            ProcessDEM(elevGrid, elevGrid_5m, utmSR)
        if not arcpy.Exists(slopeGrid):
            arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
        arcpy.sa.ExtractMultiValuesToPoints(transPts_presort, [[elevGrid_5m, 'ptZ'], [slopeGrid, 'ptSlp']]) # 9 min for ParkerRiver
        # Convert points to DataFrames
        pts_df = FCtoDF(transPts_presort, xy=True, dffields=[tID_fld,'ptZ', 'ptSlp'])
        pts_df.to_pickle(os.path.join(out_dir, 'pts_df_elev_slope.pkl'))

#%%
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

#%% Join DF to ID raster
# *** Pick up here on 7/26/17
bw_rst = JoinDFtoRaster_setvalue(trans_df, rst_transIDpath, rst_bwgrid_path, fill=fill, id_fld=tID_fld, val_fld='uBW')
trans_fc = JoinDFtoFC(trans_df, extendedTransects, tID_fld, out_fc=extTrans_fill)


# Convert pts_df to FC, both pts and trans (pts_fc, trans_fc)
# ** Takes a while **
transPts_fill = transPts_fill+'_fromDF'
#FIXME: still having problems
pts_fc = DFtoFC_large(pts_df, outFC_pts=transPts_fill, spatial_ref=utmSR, df_id=pID_fld, xy=["seg_x", "seg_y"])

if not 'pts_fc' in locals():
    pts_fc = transPts_fill = transPts_fill+'_fromDF'

# Save final SHP and FCs with null values
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, out_dir, transPts_shp+'.shp')
arcpy.FeatureClassToFeatureClass_conversion(pts_fc, home, transPts_null)

#FIX 9 points were produced that have fill (or Null) x and y. Why and how to fix?
# Look at df entries for those points
missing_xy = [98,99,100,101,102,23728,23729,23730,73507]
pts_df.loc[missing_xy]
missing_tIDs = [6,7,8,9,10,128,129,130,411]
trans_df.loc[missing_tIDs]
# The null XY values are caused by the transect not intersecting the land. Then, the clip removes them, but when I ~join~ ---look into how this happens
pts_df.seg_y.isnull()
pts_df.loc[pts_df.seg_y.isnull(), :].sort_ID
pts_df[~pts_df.seg_y.isnull()]
pts_df[~pts_df.seg_x.isnull()]
# Added df = df[~df.seg_x.isnull()] to DFtoFC()
# Manually deleted the 9 points instead of repeating the process.

if not 'trans_fc' in locals():
    trans_fc = extTrans_fill
arcpy.FeatureClassToFeatureClass_conversion(trans_fc, home, extTrans_null)
ReplaceValueInFC(extTrans_null, fill, None)

# Export the files used to run the process to code file in home dir
# os.makedirs(code_dir, exist_ok=True)
try:
    os.makedirs(code_dir)
except OSError:
    if not os.path.isdir(code_dir):
        raise
shutil.copy(os.path.join(script_path, 'TE_master_2.py'), os.path.join(code_dir, 'TE_master_2.py'))
shutil.copy(os.path.join(script_path, 'TE_ParkerRiver2014.py'), os.path.join(code_dir, 'TE_ParkerRiver2014.py'))
shutil.copy(os.path.join(script_path, 'TE_config.py'), os.path.join(code_dir, 'TE_config.py'))
shutil.copy(os.path.join(script_path, 'TE_functions.py'), os.path.join(code_dir, 'TE_functions.py'))
shutil.copy(os.path.join(script_path, 'TE_functions_arcpy.py'), os.path.join(code_dir, 'TE_functions_arcpy.py'))
