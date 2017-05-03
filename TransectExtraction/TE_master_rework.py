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
# extendedTransects...
# DeleteTempFiles()
# 1: Add XYZ from DH, DL, & Arm points within 10m of transects *SPATIAL*
if not arcpy.Exists(shoreline):
    CreateShoreBetweenInlets(barrierBoundary, inletLines, shoreline, ShorelinePts, proj_code)
inPtsDict={'ShorelinePts': ShorelinePts, 'dhPts': dhPts, 'dlPts': dlPts,
'shoreline': shoreline, 'armorLines': armorLines}
# FIXME: this could be performed mostly with PANDAS
# dunes_to_trans(pts_df, dl_df, tID_fld='sort_ID')
AddFeaturePositionsToTransects(in_trans=orig_extTrans, out_fc=extendedTransects,
    inPtsDict=inPtsDict, IDfield=tID_fld,
    proj_code=proj_code, disttolerance=pt2trans_disttolerance, home=home,
    elevGrid_5m=elevGrid_5m)

# 3: Dist2Inlet: Calc dist from inlets SPATIAL
Dist2Inlet(extendedTransects, shoreline, tID_fld, xpts='shoreline2trans')

# 4: Clip transects, get barrier widths *SPATIAL*
GetBarrierWidths(extendedTransects, barrierBoundary, shoreline, IDfield=tID_fld, out_clipped_trans='trans_clipped2island')

#%%
"""
SPATIAL: points (from transects)
"""
# 5: Create Transect Segment points and sample data *SPATIAL*
# Split transects into points
# After XTools divides dataset, run FC to numpy with explode to points?
SplitTransectsToPoints(extTrans_tidy, transPts_presort, barrierBoundary,
                       home, clippedtrans='trans_clipped2island')

# 6: Extract elev and slope at points *SPATIAL*
# Create slope grid if doesn't already exist
if not arcpy.Exists(slopeGrid):
    arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
# Extract elevation and slope at points
# arcpy.DeleteField_management(transPts_presort, ['ptZ', 'ptSlp', 'ptZmhw'])  # if reprocessing
arcpy.sa.ExtractMultiValuesToPoints(transPts_presort, [[elevGrid_5m, 'ptZ'],
                                    [slopeGrid, 'ptSlp']])
# # Save pts with elevation and slope to archived file
# pts_df.to_pickle(os.path.join(working_dir, pts_elevslope + '.pkl'))
# if os.path.exists(os.path.join(working_dir, pts_elevslope+'.pkl')):
#     # Join elevation and slope values from a previous iteration of the script
#     zpts_df = pd.read_pickle(os.path.join(working_dir, pts_elevslope + '.pkl'))
#     pts_df = FCtoDF(transPts, id_fld=pID_fld)
#     pts_df = pts_df.join(zpts_df)

#%%
"""
SPATIAL + PANDAS:
"""
#%%
# Convert transects and points to DataFrames
trans_df = FCtoDF(extendedTransects, id_fld=tID_fld)
pts_df = FCtoDF(transPts, xy=True, extra_fields=extra_fields + old_fields + repeat_fields)

# # Save dataframes to open elsewhere or later
trans_df.to_pickle(os.path.join(out_dir, 'pre_'+ extTrans_null+'.pkl'))
pts_df.to_pickle(os.path.join(out_dir,'pre_'+ transPts_null+'.pkl'))
#%% Pure Pandas ~~~
pts_df= pd.read_pickle(os.path.join(out_dir,'pre_'+ transPts_null+'.pkl'))
trans_df= pd.read_pickle(os.path.join(out_dir, 'pre_'+ extTrans_null+'.pkl'))

# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
pts_df = prep_points(pts_df, tID_fld, pID_fld, MHW)
trans_df = calc_trans_distances(trans_df)
pts_df = calc_trans_distances(pts_df)

#%%
# Beach distances and elevation
pts_df, bws_trans = calc_beach_width(pts_df, maxDH, tID_fld)
trans_df = join_columns(trans_df, bws_trans)

# Aggregate ptZmhw to max and mean and join to transPts and extendedTransects
pts_df, zmhw = aggregate_z(pts_df, MHW, tID_fld, 'ptZ')
trans_df = join_columns(trans_df, zmhw) # join new fields to transects
pts_df = join_columns(pts_df, trans_df, tID_fld) # Join transect values to pts

# # Save dataframes to open elsewhere or later
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
pts_df.to_pickle(os.path.join(out_dir, transPts_null+'.pkl'))
# pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
# trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
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

#%% # OUTPUT: Create ID raster
# arcpy.env.workspace = os.path.dirname(rst_transIDpath)
# if not arcpy.Exists(os.path.basename(rst_transIDpath)):
#     outEucAll = arcpy.sa.EucAllocation(orig_tidytrans, maximum_distance=50,
#                                        cell_size=cell_size, source_field=tID_fld)
#     outEucAll.save(os.path.basename(rst_transIDpath))
# arcpy.env.workspace = home

#%% Join DF to ID raster
bw_rst = JoinDFtoRaster_setvalue(bws_trans, rst_transIDpath, rst_bwgrid_path, fill=fill, id_fld=tID_fld, val_fld='uBW')
# bw_rst = JoinDFtoRaster_setvalue(trans_df, rst_transIDpath, rst_bwgrid_path, fill=fill, id_fld=tID_fld, val_fld='uBW')

# Convert pts_df to FC, both pts and trans (pts_fc, trans_fc)
# ** Takes a while **
transPts_fill = transPts_fill+'_fromDF'
pts_fc, trans_fc = DFtoFC_2parts(pts_df, outFC_pts=transPts_fill, trans_df=trans_df,
                        trans_fc=extendedTransects, spatial_ref=utmSR, pt_flds=pt_flds, group_flds=trans_flds)

# Save final SHP, and FCs with null values
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
