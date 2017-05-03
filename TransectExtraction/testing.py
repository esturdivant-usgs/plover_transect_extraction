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

def ShorelinePtsToTransects(extendedTransects, inPtsDict, IDfield, proj_code, pt2trans_disttolerance):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']
    shoreline = inPtsDict['shoreline']
    ShorelinePts = inPtsDict['ShorelinePts']
    arcpy.Intersect_analysis((shoreline, extendedTransects), 'SHL2trans_temp', output_type='POINT')
    shl2trans, shlfields = AddXYAttributes('SHL2trans_temp', 'SHL2trans', 'SL', proj_code)
    shlfields.append('Bslope')
    # Add lat lon and x y fields to create SHL2trans
    # Add slope from ShorelinePts to shoreline intersection with transects (which replace the XY values from the original shoreline points)
    ReplaceFields(inPtsDict['ShorelinePts'],{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(shl2trans,inPtsDict['ShorelinePts'], 'join_temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # create join_temp
    arcpy.JoinField_management(shl2trans,IDfield,'join_temp',IDfield,'slope') # join slope from join_temp (from ShorelinePts) with SHL2trans points
    arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
    arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')
    arcpy.DeleteField_management(extendedTransects, shlfields) #In case of reprocessing
    arcpy.JoinField_management(extendedTransects, IDfield, shl2trans, IDfield, shlfields)
    return extendedTransects
