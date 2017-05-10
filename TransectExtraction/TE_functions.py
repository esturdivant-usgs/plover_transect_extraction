# Transect Extraction module
# possible categories: preprocess, create, calculate

import time
import os
import collections
import pandas as pd
import numpy as np
from operator import add


def newcoord(coords, dist):
    # From: gis.stackexchange.com/questions/71645/extending-line-by-specified-distance-in-arcgis-for-desktop
    # Computes new coordinates x3,y3 at a specified distance along the
    # prolongation of the line from x1,y1 to x2,y2
    (x1,y1),(x2,y2) = coords
    dx = x2 - x1 # change in x
    dy = y2 - y1 # change in y
    linelen =np.hypot(dx, dy) # distance between xy1 and xy2
    x3 = x2 + dx/linelen * dist
    y3 = y2 + dy/linelen * dist
    return x3, y3

def list_groupcolumns(df, group_id):
    # This should return the columns in which values are consistent by transect, but it's showing that none are.
    gmin = df.groupby(group_id).min()
    gmax = df.groupby(group_id).max()
    clist=[]
    for c in df.columns.drop(group_id):
        if (gmin[c] == gmax[c]).all():
            clist.append(c)
    return(clist)
    # ne = (gmin == gmax).all()
    # ne_stacked = (gmin != gmax).all()
    # changed = ne_stacked[ne_stacked]

def join_columns(df1, df2, id_fld='ID', how='outer'):
    # id_fld
    if id_fld in df2.columns:
        df2.index = df2[id_fld] # set id_fld to index of join dataframe
        df2 = df2.drop(id_fld, axis=1) # remove id_fld from join dataframe
        df1 = df1.drop(df1.axes[1].intersection(df2.axes[1]), axis=1) # remove matching columns from target dataframe
        df1 = df1.join(df2, on=id_fld, how=how) # join df2 to df1
    else:
        df1 = df1.drop(df1.axes[1].intersection(df2.axes[1]), axis=1)
        df1 = df1.join(df2, how=how)
    return(df1)

def adjust2mhw(df, MHW, fldlist=['DH_z', 'DL_z', 'Arm_z']):
    for fld in fldlist:
        df = (df.drop(fld+'mhw', axis=1, errors='ignore')
                .join(df[fld].subtract(MHW), rsuffix='mhw'))
    return(df)

def sort_pts(df, tID_fld, pID_fld='SplitSort'):
    # Calculate pt distance from shore; use that to sort pts and create pID_fld
    # 1. set X and Y fields
    if 'SHAPE@X' in df.columns:
        df.drop(['seg_x', 'seg_y'], axis=1, inplace=True, errors='ignore')
        df.rename(index=str, columns={'SHAPE@X':'seg_x', 'SHAPE@Y':'seg_y'}, inplace=True)
    # 2. calculate pt distance to MHW
    df.reset_index(drop=True, inplace=True)
    dist_seg = np.hypot(df.seg_x - df.SL_x, df.seg_y - df.SL_y)
    df = join_columns(df, pd.DataFrame({'Dist_Seg': dist_seg}, index=df.index))
    # 3. Sort and create pID_fld (SplitSort)
    df = df.sort_values(by=[tID_fld, 'Dist_Seg']).reset_index(drop=True)
    df.index.rename(pID_fld, inplace=True)
    df.reset_index(drop=False, inplace=True)
    return(df)

def calc_trans_distances(df):
    sl2dh = np.hypot(df.SL_x - df.DH_x, df.SL_y - df.DH_y)
    sl2dl = np.hypot(df.SL_x - df.DL_x, df.SL_y - df.DL_y)
    sl2arm = np.hypot(df.SL_x - df.Arm_x, df.SL_y - df.Arm_y)
    df = join_columns(df, pd.DataFrame({'DistDH': sl2dh,
                                        'DistDL': sl2dl,
                                        'DistArm': sl2arm
                                        }, index=df.index))
    return(df)

def calc_pt_distances(df):
    pt2dh = np.hypot(df.seg_x - df.DH_x, df.seg_y - df.DH_y)
    pt2dl = np.hypot(df.seg_x - df.DL_x, df.seg_y - df.DL_y)
    pt2arm = np.hypot(df.seg_x - df.Arm_x, df.seg_y - df.Arm_y)
    df = join_columns(df, pd.DataFrame({'DistSegDH': pt2dh,
                                        'DistSegDL': pt2dl,
                                        'DistSegArm': pt2arm,
                                        'Dist_MHWbay': df.WidthPart - df.Dist_Seg
                                        }, index=df.index))
    return(df)

def prep_points(df, tID_fld, pID_fld, MHW, old2newflds={}):
    # Preprocess transect points (after running FCtoDF(transPts, xy=True))
    # 0. Rename columns
    if len(old2newflds):
        df.rename(index=str, columns=old2newflds, inplace=True)
    # Calculate pt distance from shore; use that to sort pts and create pID_fld (SplitSort)
    df = sort_pts(df, tID_fld, pID_fld)
    # Calculate pt distance from dunes and bayside shore
    df = calc_pt_distances(df)
    df = adjust2mhw(df, MHW)
    df = calc_trans_distances(df)
    return(df)

def prep_points_v1(df, tID_fld, pID_fld, old2newflds={}):
    # Preprocess transect points (after running FCtoDF(transPts, xy=True))
    # 0. Rename columns
    if len(old2newflds):
        df.rename(index=str, columns=old2newflds, inplace=True)
    # 1. set X and Y fields
    if 'SHAPE@X' in df.columns:
        df.drop(['seg_x', 'seg_y'], axis=1, inplace=True, errors='ignore')
        df.rename(index=str, columns={'SHAPE@X':'seg_x', 'SHAPE@Y':'seg_y'}, inplace=True)
    # 2. calculate distances
    dist_seg = np.hypot(df.seg_x - df.SL_x, df.seg_y - df.SL_y)
    dist_dh = np.hypot(df.seg_x - df.DH_x, df.seg_y - df.DH_y)
    dist_dl = np.hypot(df.seg_x - df.DL_x, df.seg_y - df.DL_y)
    dist_arm = np.hypot(df.seg_x - df.Arm_x, df.seg_y - df.Arm_y)
    df = join_columns(df, pd.DataFrame({'Dist_Seg': dist_seg,
                                        'DistSegDH': dist_dh,
                                        'DistSegDL': dist_dl,
                                        'DistSegArm': dist_arm,
                                        'Dist_MHWbay': df.WidthPart - dist_seg
                                        # 'DistSegDH': dist_seg - df.DistDH,
                                        # 'DistSegDL': dist_seg - df.DistDL,
                                        # 'DistSegArm': dist_seg - df.DistArm
                                        }, index=df.index))
    # 3. Sort and create pID_fld (SplitSort)
    df = df.sort_values(by=[tID_fld, 'Dist_Seg']).reset_index(drop=True)
    df.index.rename(pID_fld, inplace=True)
    df.reset_index(drop=False, inplace=True)
    return(df)

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
            ptDL['x'] = Xtran.ix[ipt] #FIXME: cannot do label indexing on <class 'pandas.indexes.numeric.Int64Index'> with these indexers [nan] of <type 'float'>'
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

def aggregate_z(df, MHW, id_fld, zfld):
    # Aggregate ptZmhw to max and mean and join to transects
    df = (df.drop(zfld+'mhw', axis=1, errors='ignore')
            .join(df[zfld].subtract(MHW), rsuffix='mhw'))
    # get mean only if > 80% of points have elevation
    meanf = lambda x: x.mean() if float(x.count())/x.size > 0.8 else np.nan
    zmhw = df.groupby(id_fld)[zfld+'mhw'].agg({'mean_Zmhw':meanf,
                                               'max_Zmhw':np.max})
    df = join_columns(df, zmhw, id_fld)
    return(df, zmhw)
