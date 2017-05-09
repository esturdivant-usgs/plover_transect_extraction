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


#%% Replace SplitTransectsToPoints()
# WidthFull
in_trans ='ParkerRiver2014_trans_clip'
out_clipped ='ParkerRiver2014_clip2island'
arcpy.Clip_analysis(os.path.join(home, in_trans), os.path.join(home, barrierBoundary), out_clipped) # ~30 seconds
verts_df = FCtoDF(out_clipped, xy=True, explode_to_points=True)
verts_df.to_pickle(os.path.join(out_dir, out_clipped+'.pkl'))
verts_df = pd.read_pickle(os.path.join(out_dir, out_clipped+'.pkl'))

diff = lambda x: x.max() - x.min()
dx = verts_df.groupby(tID_fld)['SHAPE@X'].agg({'dx': diff})
dy = verts_df.groupby(tID_fld)['SHAPE@Y'].agg({'dy': diff})
widthfull = np.hypot(dx, dy)



verts_df.columns
verts_df[verts_df['sort_ID']==164]['SHAPE@X']
verts_df[verts_df['sort_ID']==164]['SHAPE@Y']

# arcpy.FeatureVerticesToPoints_management(out_clipped, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect # ~20 seconds
# verts_df = FCtoDF("verts_temp", explode_to_points=True)
# verts_trans = vert_df.groupby(tID_fld)['SHAPE@X', 'SHAPE@Y']





#%% Replace PointMetricsToTransects()

#V1:
 def dunes_to_trans(pts_df, dl_df, tID_fld='sort_ID', xyzflds=['SHAPE@X', 'SHAPE@Y', 'dlow_z'], prefix='DL'):
    #FIXME: outputs all NaN values right now
    # dl_df = FCtoDF(dlPts, xy=True)
    trans_df = pts_df.groupby(tID_fld).first()
    dlpts = pd.DataFrame(np.nan, index=trans_df.index, columns=dl_df.columns)
    # loop through transects
    for tID, tran in trans_df.iterrows(): # tran = trans_df.iloc[tID]
        # tID = 100
        # tran = trans_df.iloc[tID]
        Ytran = pts_df[pts_df[tID_fld] == tID]['seg_y']
        Xtran = pts_df[pts_df[tID_fld] == tID]['seg_x']
        # get distance between transect and every dlow point
        dltmp = pd.Series(np.nan, index=dl_df.index)
        for di, row in dl_df.iterrows():
            mindist = np.hypot(Xtran - row[xyzflds[0]], Ytran - row[xyzflds[1]]).min()
            dltmp[di] = mindist if mindist < 25 else np.nan
        # get index of minimum distance
        try:
            dlpts.ix[tID] = dl_df.iloc[dltmp.idxmin()]
        except:
            print('NaN?: {}, {}'.format(tID, dltmp.idxmin()))
            pass
    xyz = pd.concat([pd.Series(dlpts[xyzflds[0]], name=prefix+'_x'),
                     pd.Series(dlpts[xyzflds[1]], name=prefix+'_y'),
                     pd.Series(dlpts[xyzflds[2]], name=prefix+'_z')], axis=1)
    pts_df = (pts_df.drop(pts_df.axes[1].intersection(xyz.axes[1]), axis=1)
                    .join(xyz, on=tID_fld, how='outer'))
    # dlpts.rename(index=str, columns={xyzflds[0]:prefix+'_x', xyzflds[1]:prefix+'_y'}, inplace=True)
    return(pts_df, dlpts)
    # DFtoFC(dlpts, dl2trans_fc, spatial_ref, tID_fld, xy=["x", "y"], keep_fields=['z'])




#FIXME: return all fields from input, not just xyz
dl_df = FCtoDF(dlPts, xy=True)
dh_df = FCtoDF(dhPts, xy=True)


pts_df, dl2trans = dunes_to_trans(pts_df, dl_df)#, tID_fld=tID_fld, fields='all', zfld='dlow_z')
pts_df, dh2trans = dunes_to_trans(pts_df, dh_df, tID_fld=tID_fld, fields='all', zfld='dhi_z')



dl2trans_fc = 'test_DL2trans_fromPD'
DFtoFC(dl2trans, dl2trans_fc, utmSR, tID_fld, xy=["x", "y"], keep_fields=[dl2trans.columns])
DFtoFC(dh2trans, dh2trans_fc, utmSR, tID_fld, xy=["x", "y"], keep_fields=[dh2trans.columns])





#%% Rewrite ShorelinePtsToTransects() to use pandas

def ShorelineToTrans_PD(extendedTransects, trans_df, inPtsDict, IDfield, proj_code, disttolerance=25, fill=-99999):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']
    shoreline = inPtsDict['shoreline']
    ShorelinePts = inPtsDict['ShorelinePts']
    shl2trans = 'SHL2trans_temp'
    shljoin = 'shljoin_temp'
    home = arcpy.env.workspace
    arcpy.Intersect_analysis((shoreline, extendedTransects), shl2trans, output_type='POINT')
    #FIXME: shljoin = JOIN closest feature in ShorelinePts to shl2trans
    #fmap = 'sort_ID "sort_ID" true true false 2 Short 0 0 ,First,#,SHL2trans_temp,sort_ID,-1,-1; ID "ID" true true false 4 Float 0 0 ,First,#,\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\Delmarva\Assateague\2014\Assateague2014.gdb\Assateague2014_SLpts,ID,-1,-1'
    # arcpy.SpatialJoin_analysis(shl2trans, os.path.join(home, ShorelinePts), 'join_temp','#','#', fmap, "CLOSEST", pt2trans_disttolerance) # create join_temp
    shljoin_df = FCtoDF(shljoin, xy=True, dffields=[IDfield, 'slope', 'Distance'], fid=True)
    shljoin_df.rename(index=str, columns={'slope':'Bslope', 'SHAPE@X':'SL_x','SHAPE@Y':'SL_y', 'OID@':'slpts_id'}, inplace=True)
    for i, row in shljoin_df.iterrows():
        if row['Distance'] > disttolerance:
            shljoin_df.ix[i, 'Bslope'] = fill
    shljoin_df.drop('Distance', axis=1)
    shljoin_df.index.name = id_fld
    trans_df = join_columns(trans_df, shljoin_df)
    # JoinDFtoFC(shljoin_df, extendedTransects, IDfield)
    # return extendedTransects
    return shljoin_df
