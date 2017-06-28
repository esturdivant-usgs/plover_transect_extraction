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



pts_df = pd.read_pickle(os.path.join(out_dir,transPts_null+'.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))


# Try to merge Forsythe2014
pts_df = pd.read_excel(os.path.join(out_dir,transPts_fill+'_noTrans'+'.xlsx'))
trans_df = pd.read_excel(os.path.join(out_dir,extTrans_fill+'.xlsx'))
# save as pickle
pts_df.to_pickle(os.path.join(out_dir,transPts_fill+'_noTrans'+'.pkl'))
trans_df.to_pickle(os.path.join(out_dir, 'trans_df.pkl'))

pts_df = pd.read_pickle(os.path.join(out_dir,transPts_fill+'_noTrans'+'.pkl'))
trans_df = pd.read_pickle(os.path.join(out_dir, 'trans_df.pkl'))
# replace 9999 fill with np.nan
for col, ser in pts_df.iteritems():
    ser.replace(9999, np.nan, inplace=True)
for col, ser in trans_df.iteritems():
    ser.replace(9999, np.nan, inplace=True)
pts_df.to_pickle(os.path.join(out_dir,transPts_fill+'_noTrans'+'.pkl'))
trans_df.to_pickle(os.path.join(out_dir, 'trans_df.pkl'))
# join
pts_df = join_columns(pts_df, trans_df, tID_fld) # Join transect values to pts
#%% Save dataframes to open elsewhere or later
trans_df.to_pickle(os.path.join(out_dir, extTrans_null+'.pkl'))
pts_df.to_pickle(os.path.join(out_dir, transPts_null+'.pkl'))

if not pID_fld in pts_df.columns:
    pts_df.reset_index(drop=False, inplace=True)
pts_df.to_csv(os.path.join(out_dir, transPts_fill +'_pd.csv'), na_rep=fill, index=False)

pts_df.to_excel(os.path.join(out_dir, transPts_fill +'_pd.xlsx'), na_rep=fill, index=False)




in_trans=extendedTransects
tID_fld='sort_ID'
tcurs = arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld))
trow = tcurs.next()
trow = tcurs.next()
trow = tcurs.next()
trow = tcurs.next()
trow = tcurs.next()
transect = trow[0]
tID = trow[1] # 5

start=time.clock()

print_duration(start)


df.to_pickle(os.path.join(out_dir, 'sl2trans_df.pkl'))
df = pd.read_pickle(os.path.join(out_dir, 'sl2trans_df.pkl'))
df.head()

def get_closest_point(df, transect, in_pts, field, proximity):
    shortest_dist = float(proximity)
    found = False
    for prow in arcpy.da.SearchCursor(in_pts, ["SHAPE@X", "SHAPE@Y", field, "OID@"]):
        in_pt = arcpy.Point(X=prow[0], Y=prow[1], ID=prow[3])
        if transect.distanceTo(in_pt) < shortest_dist:
            shortest_dist = transect.distanceTo(in_pt)
            pt = in_pt
            found=True
    if found:
        df.loc[tID, [prefix+'_x', prefix+'_y', field]] = [pt.X, pt.Y, prow[2]]
    return(df, found)


trans_df
dunepts_df = FCtoDF(in_pts dffields=['easting','northing','z'])
for tID, tran in trans_df.iterrows():
    for


shortest_dist = float(proximity)
found = False
for prow in arcpy.da.SearchCursor(in_pts, ["SHAPE@X", "SHAPE@Y", field, "OID@"]):
    in_pt = arcpy.Point(X=prow[0], Y=prow[1], ID=prow[3])
    if transect.distanceTo(in_pt) < shortest_dist:
        shortest_dist = transect.distanceTo(in_pt)
        pt = in_pt
        found=True
if found:
    df.loc[tID, [prefix+'_x', prefix+'_y', field]] = [pt.X, pt.Y, prow[2]]
return(df, found)



def calc_beach_width(pts_df, maxDH=2.5, tID_fld='sort_ID'):
    # Calculate beach width and height from MHW (uBW, uBH) from dataframe of transPts
    # get transects DF or convert pts_df to trans
    trans_df = pts_df.groupby(tID_fld).first()
    # Initialize uBW and uBH series
    uBW = pd.Series(np.nan, index=trans_df.index, name='uBW')
    uBH = pd.Series(np.nan, index=trans_df.index, name='uBH')
    feat = pd.Series(np.nan, index=trans_df.index, name='ub_feat') # dtype will 'object'
    # loop through transects
    for tID, tran in trans_df.iterrows():
        # get upper limit of beach (dlow or equivalent)
        if not np.isnan(tran.DL_x):
            iDL = {'x':tran['DL_x'], 'y':tran['DL_y'],
                   'z':tran['DL_zmhw'], 'ub_feat':'DL'}
        elif tran.DH_zmhw <= maxDH:
            iDL = {'x':tran['DH_x'], 'y':tran['DH_y'],
                   'z':tran['DH_zmhw'], 'ub_feat':'DH'}
        elif not np.isnan(tran.Arm_x):
            iDL = {'x':tran['Arm_x'], 'y':tran['Arm_y'],
                   'z':tran['Arm_zmhw'], 'ub_feat':'Arm'}
        else: # If there is no DL equivalent, BW and BH = null
            uBW[tID] = uBH[tID] = np.nan
            continue
        # Convert iDL to ptDL (also elevation from transPt instead of from dune point?)
        Ytran = pts_df[pts_df[tID_fld] == tID]['seg_y']
        Xtran = pts_df[pts_df[tID_fld] == tID]['seg_x']
        ipt = np.hypot(Xtran - iDL['x'], Ytran - iDL['y']).idxmin()
        ptDL = iDL
        try:
            ptDL['x'] = Xtran.ix[ipt]
            ptDL['y'] = Ytran.ix[ipt]
            # ptDL = iDL if np.isnan(ipt) else {'x':Xtran[ipt], 'y':Ytran[ipt], 'z':iDL['z']}
        except TypeError:
            ptDL['x'] = np.nan
            ptDL['y'] = np.nan
        if np.isnan(ipt):
            print('Transect {}: Despite that DL equiv was found, ipt is nan.'.format(tID))
        if np.isnan(ptDL['x']):
            print('ptDL["x"] is NaN')
            if not np.isnan(tran.Arm_x): # elseif isnan(Ae) == 0 & isnan(DLe) == 1,
                ptDL = {'x':tran['Arm_x'], 'y':tran['Arm_y'], 'z':tran['Arm_zmhw'], 'ub_feat':'Arm'}
        elif not np.isnan(tran.Arm_x): # if isnan(Ae) == 0 & isnan(DLe) == 0,
            bw1 = np.hypot(tran.SL_x - ptDL['x'], tran.SL_y - ptDL['y'])
            bw2 = np.hypot(tran.SL_x-tran.Arm_x, tran.SL_y-tran.Arm_y)
            if bw2 < bw1:
                ptDL = {'x':tran['Arm_x'], 'y':tran['Arm_y'], 'z':tran['Arm_zmhw'], 'ub_feat':'Arm'}
        # Get beach width
        uBW[tID] = np.hypot(tran.SL_x - ptDL['x'], tran.SL_y - ptDL['y']) # problem: Xout
        uBH[tID] = ptDL['z'] # Use elevation from transPt instead of from dune point?
        feat[tID] = ptDL['ub_feat'] # dtype='object'
    # Add new uBW and uBH fields to trans_df
    bw_df = pd.concat([uBW, uBH, feat], axis=1)
    pts_df = (pts_df.drop(pts_df.axes[1].intersection(bw_df.axes[1]), axis=1)
                    .join(bw_df, on=tID_fld, how='outer'))
    return(pts_df, bw_df)

#%% Troubleshoot JoinFields in JoinDFtoFC in DFtoFC_large

# 2. Create FC of transect fields by joining back to extendedTransects
if verbose:
    print('Converting points DF to FC...')
group_fc = JoinDFtoFC(trans_df, trans_fc, group_id, out_fc=trans_fc+'_fromDF', fill=fill, verbose=verbose)
# 3. Join transect fields to points in ArcPy
missing_fields = fieldsAbsent(outFC_pts, group_flds)
arcpy.JoinField_management(outFC_pts, group_id, group_fc, group_id, missing_fields)



# 3. Join transect fields to points in ArcPy
missing_fields = fieldsAbsent(outFC_pts, group_flds)
arcpy.JoinField_management(outFC_pts, group_id, group_fc, group_id, missing_fields)
return(outFC_pts, group_fc)









#FIXME: return all fields from input, not just xyz
dl_df = FCtoDF(dlPts, xy=True)
dh_df = FCtoDF(dhPts, xy=True)


pts_df, dl2trans = dunes_to_trans(pts_df, dl_df)#, tID_fld=tID_fld, fields='all', zfld='dlow_z')
pts_df, dh2trans = dunes_to_trans(pts_df, dh_df, tID_fld=tID_fld, fields='all', zfld='dhi_z')



dl2trans_fc = 'test_DL2trans_fromPD'
DFtoFC(dl2trans, dl2trans_fc, utmSR, tID_fld, xy=["x", "y"], keep_fields=[dl2trans.columns])
DFtoFC(dh2trans, dh2trans_fc, utmSR, tID_fld, xy=["x", "y"], keep_fields=[dh2trans.columns])
