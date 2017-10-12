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

home = os.path.join(local_home, '{site}{year}.gdb'.format(**SiteYear_strings))
if sys.platform == 'win32':
    arcpy.env.workspace=home
out_dir = os.path.join(local_home, 'scratch')



pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
trans_df1 = pd.read_pickle(os.path.join(out_dir, extTrans_null+'_prePts.pkl'))
trans_df = join_columns_id_check(trans_df, trans_df1, tID_fld)
pts_df[pts_df['sort_ID']==133].head()
trans_df.loc[270]
trans_df.loc[270]

# pts_df1 = join_columns_orig(pts_df, trans_df1, tID_fld) # Join transect values to pts
pts_df1 = join_columns(pts_df, trans_df1, tID_fld) # Join transect values to pts

trans_df1.loc[270]
pts_df1[pts_df1['sort_ID']==133].head()
pts_df1[pts_df1['sort_ID']==270].head()






pts_df1.to_pickle(os.path.join(out_dir, transPts_null+'.pkl'))
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))

"""
beach width
"""

"""
Dist2Inlet
"""
shoreline
in_trans = extendedTransects
inletLines

df = pd.DataFrame(columns=[tID_fld, 'Dist2Inlet'])
inlets = arcpy.CopyFeatures_management(inletLines, arcpy.Geometry())

cursor = arcpy.da.SearchCursor(shoreline, ("SHAPE@"))

row = cursor.next()
line = row[0]

for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
    transect = trow[0]
    tID = trow[1]
    if not line.disjoint(transect): #line and transect overlap
        # cut shoreline with transect
        seg = line.cut(transect)
        # get length for only segs that touch inlets
        lenR = seg[0].length if not all(seg[0].disjoint(i) for i in inlets) else np.nan
        lenL = seg[1].length if not all(seg[1].disjoint(i) for i in inlets) else np.nan
        mindist = np.nanmin([lenR, lenL])
        df = df.append({tID_fld:tID, 'Dist2Inlet':mindist}, ignore_index=True)
        break


for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
    transect = trow[0]
    tID = trow[1]
    if not line.disjoint(transect):
        break
shoreseg = line.cut(transect)

#%% TESTING 2
shoreline
in_trans = extendedTransects
inletLines
inlets = arcpy.CopyFeatures_management(inletLines, arcpy.Geometry())
shorelines = arcpy.CopyFeatures_management(shoreline, arcpy.Geometry())
line = shorelines[0]
tcursor = arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld))

trow = tcursor.next()
transect = trow[0]
tID = trow[1]
print(tID) # 11

shoreseg = line.cut(transect)
lenR = shoreseg[0].length if not all(shoreseg[0].disjoint(i) for i in inlets) else np.nan
lenL = shoreseg[1].length if not all(shoreseg[1].disjoint(i) for i in inlets) else np.nan
