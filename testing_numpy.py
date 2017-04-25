#!python27
'''
Configuration file for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 11/22/2016
'''
import os
import time
import sys
import pandas as pd
import numpy as np
# path to TransectExtraction module
if sys.platform == 'win32':
    sys.path.append(r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction") # path to TransectExtraction module
    import arcpy
    import pythonaddins
    from TE_functions_arcpy import *
if sys.platform == 'darwin':
    sys.path.append('/Users/esturdivant/GitHub/plover_transect_extraction/TransectExtraction')
from TE_config import *
from TE_functions import *
import matplotlib.pyplot as plt
import matplotlib
matplotlib.style.use('ggplot')

# %% What happens in Arc
# fnamesPts = [f.name for f in arcpy.ListFields(transPts)]
# extTransArr = arcpy.da.FeatureClassToNumPyArray(os.path.join(home,transPts), fnamesPts + ['SHAPE@X','SHAPE@Y'], null_value=fill)
# arr = np.load(os.path.join(out_dir, 'trans_arr_0323.npy'))
# df2 = pd.DataFrame.from_records(arr)

# %% Work with dataframes exported from ArcMap
pts_df = pd.read_pickle(os.path.join(out_dir, transPts_null+'_slim0403.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'_slim0403.pkl'))

# %%
trans_in = 400
pts_set = pts_df[pts_df[tID_fld] == trans_in]

pts_set.plot(x='Dist_Seg', y='ptZmhw')

plt.figure(figsize=(7,5)) # Set the size of your figure, customize for more subplots
pts_set.scatter(x='DistDH', y='DH_zMHW')

plt.title('Island cross-section')
plt.xlabel('Distance from shore (m)')
plt.ylabel('Elevation (m)')

plt.show()

# pts_set.plot()
ax = fig.add_subplot(111)
ax.set_xlabel('Island cross-section (m)', fontsize = 12)
ax.set_ylabel('Elevation (m)', fontsize = 12)

pts_set[['Dist_Seg', 'ptZmhw']].plot()
ax.plot(pts_set['Dist_Seg'], pts_set['ptZmhw'], color='c', linestyle='-', linewidth = 1)


ax.plot(xaxis, pts_set['low-res shl'], color='b', linestyle='--', linewidth = 2, marker='|', markersize=8, markeredgewidth=2)
ax.plot(xaxis, df['high-res shl'], color='b', linestyle='-', linewidth = 2, marker='o', markeredgewidth=0)
ax.plot(xaxis, df['low-res dhi'], color='m', linestyle='--', linewidth = 2, marker='o', markeredgewidth=0)
ax.plot(xaxis, df['high-res dhi'], color='m', linestyle='-', linewidth = 2, marker='o', markeredgewidth=0)
ax.plot(xaxis, df['low-res dlo'], color='k', linestyle='--', linewidth = 2, marker='o', markeredgewidth=0)
ax.plot(xaxis, df['high-res dlo'], color='k', linestyle='-', linewidth = 2, marker='o', markeredgewidth=0)
ax.axis([10, 55, -2, 10]) # range of both axes: [x min, x max, y min, y max]
#ax.axis('equal')
ax.axis('scaled')
plt.show()

fig.clear()

# %% Try to perform PointMetricsToTransects with pandas
pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
#
dl_df = FCtoDF(dlPts, xy=True)
dl_df = pd.read_pickle(os.path.join(out_dir, 'dlows.pkl'))

pts_df2, dl2trans = dunes_to_trans(pts_df.ix[4000:4500,:], dl_df)

dl2trans.describe()

def dunes_to_trans(pts_df, dl_df, tID_fld='sort_ID', xyzflds=['SHAPE@X', 'SHAPE@Y', 'dlow_z'], prefix='DL'):
    #FIXME: Could probably be much more efficient
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
            distances = np.hypot(Xtran - row[xyzflds[0]], Ytran - row[xyzflds[1]])
            print(distances)
            mindist = distances.min()
            dltmp[di] = mindist if mindist < 25 else np.nan
        # get index of minimum distance
        try:
            dlpts.ix[tID] = dl_df.iloc[dltmp.idxmin()]
            print('tID {}: {}, {}'.format(tID, dltmp.idxmin(), dltmp.min()))
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






# %%
