#!python27
'''
Configuration file for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 11/22/2016
'''
import numpy as np
import pandas as pd
import os
import csv
import sys
sys.path.append('/Users/esturdivant/GitHub/plover_transect_extraction/TransectExtraction')
# from TE_config_Forsythe2010 import *

# %%
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2010',
                    'region': 'NewJersey',
                    'code': 'ebf10',
                    'MHW':0.43,
                    'MLW':-0.61,
                    'MTL':None}
dMHW = - SiteYear_strings['MHW']                        # Beach height adjustment
if sys.platform == 'darwin':
    volume = '/Volumes'
elif sys.platform == 'win32':
    volume = r'\\IGSAGIEGGS-CSGG'
elif sys.platform == 'linux' or 'linux2':
    volume = '/Volumes'
else:
    print("platform is '{}'. Add this to the options.".format(os.name))
# out_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)
out_dir = os.path.join(volume, 'Thieler_Group', 'Commons_DeepDive', 'DeepDive',
    SiteYear_strings['region'], SiteYear_strings['site'], SiteYear_strings['year'], 'Extracted_Data')
temp_dir = os.path.join(volume, 'Thieler_Group', 'Commons_DeepDive', 'DeepDive',
    SiteYear_strings['region'], SiteYear_strings['site'], SiteYear_strings['year'], 'temp')
site_dir = os.path.join(volume, 'Thieler_Group', 'Commons_DeepDive', 'DeepDive',
    SiteYear_strings['region'], SiteYear_strings['site'])
SiteYear_strings['site_dir'] = site_dir
home_gdb = '{site}{year}.gdb'.format(**SiteYear_strings)
SiteYear_strings['home'] = home = os.path.join(SiteYear_strings['site_dir'], SiteYear_strings['year'], home_gdb)
working_dir = os.path.join(SiteYear_strings['site_dir'], SiteYear_strings['year'], 'working')

transPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)


# %%
trans_spatial_inputs = ['sort_ID', 'SL_x', 'SL_y', 'DL_x', 'DL_y', 'DH_z', 'Arm_x',
    'Arm_y', 'Arm_z', 'WidthPart']
pts_spatial_inputs = ['seg_x', 'seg_y']
calculated = ['DL_zMHW', 'DH_zMHW', 'Arm_zMHW',
    'DistDH', 'DistDL', 'DistArm',
    'MLW_x','MLW_y',
    'bh_mhw','bw_mhw', 'bh_mlw','bw_mlw',
    'CP_x','CP_y','CP_zMHW']

# %% What happens in Arc
# fnamesPts = [f.name for f in arcpy.ListFields(transPts)]
# extTransArr = arcpy.da.FeatureClassToNumPyArray(os.path.join(home,transPts), fnamesPts + ['SHAPE@X','SHAPE@Y'], null_value=fill)
# arr = np.load(os.path.join(out_dir, 'trans_arr_0323.npy'))
# df2 = pd.DataFrame.from_records(arr)

# %% Work with dataframes exported from ArcMap
# trans_df = FCtoDF(extendedTransects) # Produce Data Frame of transect_fields
# trans_df.to_pickle(os.path.join(out_dir,'trans_df.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir,'trans_df.pkl'))
# pts_df = FCtoDF(transPts, id_field='SplitSort')
# pts_df.to_pickle(os.path.join(out_dir,'pts_df.pkl'))
pts_df = pd.read_pickle(os.path.join(out_dir,'pts_df.pkl'))
# pts_final.to_pickle(os.path.join(out_dir,transPts_fill+'.pkl'))
pts_final = pd.read_pickle(os.path.join(out_dir, transPts_fill+'.pkl'))

# %% Join transects to pts using pandas
# List fields in extendedTransects that are in transPts
trans_df = trans_df.drop('sort_ID', axis=1)
pts_df = pts_df.drop('Autogen', axis=1)
tid_field = 'sort_ID'
pid_field = 'SplitSort'
pts_final = join_with_dataframes(trans_df, pts_df, tid_field, pid_field)
pts_final.axes[1]
pts_df.axes[1]

# %% Join pts values back to transects
# Use split-apply-combine
# by_id = pts_df.groupby(tid_field)
zmhw = pts_df.groupby(tid_field)['ptZmhw'].agg([np.mean, np.max])
zmhw.rename(columns={'mean':'mean_Zmhw', 'amax':'max_Zmhw'}, inplace=True)
trans_zjoin = trans_df.join(zmhw,  how='outer')
trans_zjoin

# how to add field with simple conversion from other field
MHW = SiteYear_strings['MHW']
MHW = 1
pts_df['ptZ']
pts_df['ptZ'].subtract(MHW)
pts_df.join(pts_df['ptZ'].subtract(MHW), rsuffix='mhw')


# %% Save
writer = pd.ExcelWriter(os.path.join(out_dir, transPts_fill +'.xlsx'))
pts_final.to_excel(writer,'Sheet1')
writer.save()
with pd.ExcelWriter(os.path.join(out_dir, transPts_fill +'.xlsx')) as writer:
    pts_final.to_excel(writer,'Sheet1')
    writer.save()

df.Dist_Seg = np.hypot(df.seg_x - df.SL_easting, df.seg_y - df.SL_northing)
df.Dist_MHWbay = df.WidthPart - df.Dist_Seg
df.DistSegDH = df.Dist_Seg - df.DistDH
df.DistSegDL = df.Dist_Seg - df.DistDL
df.DistSegArm = df.Dist_Seg - df.DistArm
