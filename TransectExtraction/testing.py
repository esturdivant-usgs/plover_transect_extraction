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

def geom_shore2trans(transect, tID, shoreline, in_pts, slp_fld):
    # for input transect geometry, get slope at nearest shoreline point and XY at intersect
    # 1 second per transect for ~2000 input points
    slp = np.nan
    slxpt = arcpy.Point(np.nan, np.nan)
    for srow in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
        sline = srow[0] # polyline geometry
        # Set SL_x and SL_y to point where transect intersects shoreline
        if not transect.disjoint(sline):
            slxpt = transect.intersect(sline, 1)[0]
    # Get the closest shoreline point for the slope value
    shortest_dist = float(proximity)
    # found = False
    for prow in arcpy.da.SearchCursor(in_pts, [slp_fld, "SHAPE@"]):
        pt_distance = transect.distanceTo(prow[1])
        if pt_distance < shortest_dist:
            shortest_dist = pt_distance
            # found=True
            # print('slope: {}'.format(prow[0]))
            slp = prow[0]
    return(tID, [slxpt.X, slxpt.Y, slp])

start=time.clock()
newrow = shorelineSlope2trans(transect, tID, shoreline, in_pts, slp_fld)
print_duration(start)

def add_shorelinePts2Trans(in_trans, in_pts, shoreline, prefix='SL', tID_fld='sort_ID', snaptoline_on=False, proximity=25, verbose=True):
    start = time.clock()
    fmapdict = find_similar_fields(prefix, in_pts, ['slope'])
    slp_fld = fmapdict['slope']['src']
    df = pd.DataFrame(columns=[prefix+'_x', prefix+'_y', 'Bslope'], dtype='float64')
    df.index.name = tID_fld
    for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = trow[0]
        tID = trow[1]
        newrow = shorelineSlope2trans(transect, tID, shoreline, in_pts, slp_fld)
        df.loc[newrow[0], ['SL_x', 'SL_y', 'Bslope']] = newrow[1]
        if verbose:
            if tID % 100 < 1:
                print('Duration at transect {}: {}'.format(tID, print_duration(start, True)))
    print_duration(start)
    return(df)


in_trans=extendedTransects
in_pts=ShorelinePts
shoreline = shoreline
prefix='SL'
tID_fld='sort_ID'
# slp_fld = 'Bslope'
snaptoline_on=False
proximity=25
verbose=True




df.to_pickle(os.path.join(out_dir, 'sl2trans_df.pkl'))
df = pd.read_pickle(os.path.join(out_dir, 'sl2trans_df.pkl'))
df.head()



scurs = arcpy.da.SearchCursor(shoreline, ("SHAPE@"))
srow = scurs.next()
sline = srow[0]
transect.disjoint(srow[0]) # transect 5 intersects first shoreline
slxpt = transect.intersect(sline, 1)[0]
shortest_dist = float(proximity)
found = False
for prow in arcpy.da.SearchCursor(in_pts, [slp_fld, "SHAPE@"]):
    pt_distance = transect.distanceTo(prow[1])
    if pt_distance < shortest_dist:
        shortest_dist = pt_distance
        found=True
        # print('slope: {}'.format(prow[0]))
        df.loc[tID, ['Bslope']] = [prow[0]]

if found:
    df.loc[tID, ['Bslope']] = [prow[0]]

for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
    transect = trow[0]
    tID = trow[1]
    for srow in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
        sline = srow[0] # geometry which contains lines
        if not sline.disjoint(transect):
            # get intersect of shoreline and transect
            slxpt = sline.intersect(transect, 1)
            break

df, found = get_closest_point(df, transect, in_pts, slp_fld, proximity)
if found:
    df.loc[tID, [prefix+'_x', prefix+'_y']] = [slxpt.X, slxpt.Y, np.nan]
if not found:
    df.loc[tID, [prefix+'_x', prefix+'_y', 'slope']] = [slxpt.X, slxpt.Y, np.nan]


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






def ShorelinePtsToTransects(extendedTransects, inPtsDict, IDfield, proj_code, disttolerance=25):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']

arcpy.Intersect_analysis((shoreline, in_trans), 'SHL2trans_temp', output_type='POINT')
shl2trans, shlfields = AddXYAttributes('SHL2trans_temp', 'SHL2trans', 'SL', proj_code)
shlfields.append('Bslope')
# Add lat lon and x y fields to create SHL2trans
# Add slope from ShorelinePts to shoreline intersection with transects (which replace the XY values from the original shoreline points)
ReplaceFields(in_pts,{'ID':'OID@'},'SINGLE')
arcpy.SpatialJoin_analysis(shl2trans, in_pts, 'join_temp','#','#','#',"CLOSEST", '{} METERS'.format(proximity)) # create join_temp
arcpy.JoinField_management(shl2trans,IDfield,'join_temp',IDfield,'slope') # join slope from join_temp (from ShorelinePts) with SHL2trans points
arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')
arcpy.DeleteField_management(in_trans, shlfields) #In case of reprocessing
arcpy.JoinField_management(in_trans, IDfield, shl2trans, IDfield, shlfields)
    return





for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@", tID_fld)):
    transect = row[0]
    tID = row[1]
    # get intersect of shoreline and transect
    buff = transect.buffer(proximity)
    shortest_dist = float(proximity)
    found = False
    for prow in arcpy.da.SearchCursor(in_pts, ["SHAPE@X", "SHAPE@Y", z_fld, "OID@"]):
        in_pt = arcpy.Point(X=prow[0], Y=prow[1], Z=prow[2], ID=prow[3])
        # if not buff.disjoint(in_pt):
        if transect.distanceTo(in_pt) < shortest_dist:
            shortest_dist = transect.distanceTo(in_pt)
            pt = in_pt
            found = True
    if found:
        newrow = {tID_fld:tID, prefix+'_x':pt.X, prefix+'_y':pt.Y, prefix+'_z':pt.Z, prefix+'_dist2tran':shortest_dist}
        df = df.append(newrow, ignore_index=True)
    if verbose:
        if tID % 20 < 1:
            print('Progress check at {}...'.format(tID))
            duration = print_duration(start)
df.index = df[tID_fld]
df.drop(tID_fld, axis=1, inplace=True)
duration = print_duration(start)
return(df)


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

def ShoreIntersectToTrans_PD(trans_df, shljoin, IDfield, disttolerance=25, fill=-99999):
    shljoin_df = FCtoDF(shljoin, xy=True, dffields=[IDfield, 'slope', 'Distance'], fid=True)
    shljoin_df.rename(index=str, columns={'slope':'Bslope', 'SHAPE@X':'SL_x','SHAPE@Y':'SL_y', 'OID@':'slpts_id'}, inplace=True)
    for i, row in shljoin_df.iterrows():
        if row['Distance'] > disttolerance:
            shljoin_df.ix[i, 'Bslope'] = fill
    shljoin_df = shljoin_df.drop('Distance', axis=1)
    shljoin_df.index.name = IDfield
    trans_df = join_columns(trans_df, shljoin_df, id_fld=IDfield)
    # JoinDFtoFC(shljoin_df, extendedTransects, IDfield)
    # return extendedTransects
    return(trans_df, shljoin_df)




#%% Troubleshoot JoinFields in JoinDFtoFC in DFtoFC_large

# 2. Create FC of transect fields by joining back to extendedTransects
if verbose:
    print('Converting points DF to FC...')
group_fc = JoinDFtoFC(trans_df, trans_fc, group_id, out_fc=trans_fc+'_fromDF', fill=fill, verbose=verbose)
# 3. Join transect fields to points in ArcPy
missing_fields = fieldsAbsent(outFC_pts, group_flds)
arcpy.JoinField_management(outFC_pts, group_id, group_fc, group_id, missing_fields)

# JoinDFtoFC
if not target_id:
    target_id=join_id
# Convert DF to Table
tbl = os.path.join(arcpy.env.workspace, os.path.basename(in_fc) + 'join_temp')
DFtoTable(df, tbl)
# Copy the input FC to initialize the FC to be joined
if not len(out_fc): # if out_fc is blank,
    out_fc = in_fc
else:
    arcpy.FeatureClassToFeatureClass_conversion(in_fc, arcpy.env.workspace, out_fc)
# Delete fields from target FC
if not len(join_fields): # fields to delete from target
    join_fields = df.columns.drop([target_id]+target_fields, errors='ignore') #arr.dtype.names
    # keep_flds = target_id + target_fields
else:
    try:
        join_fields.remove(target_id)
    except ValueError:
        pass
keep_flds = [x.name for x in arcpy.ListFields(out_fc) if not x.name in join_fields] # fields that should not be deleted
# keep_flds += [x.name for x in arcpy.ListFields(out_fc) if x.required]
DeleteExtraFields(out_fc, keep_flds)
# arcpy.DeleteField_management(out_fc, join_fields)
# for fld in join_fields:
#     if not fld in target_fields and not fld == target_id:
#         try: #if fieldExists(targetfc, dest):
#             arcpy.DeleteField_management(out_fc, fld)
#         except:
#             pass
# Perform join
if verbose:
    print('Performing join...')
arcpy.JoinField_management(out_fc, target_id, tbl, join_id, join_fields)

#%% Replace JoinDFtoFC() using da.ExtendTable()
# def DFtoTable(df, tbl, fill=-99999):
arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
arcpy.Delete_management(tbl)
arcpy.da.NumPyArrayToTable(arr, tbl)
    # return(tbl)

# Could use arcpy.da.ExtendTable() to join DF instead...
arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
# need to MakeTableView_management()?
arcpy.da.ExtendTable(in_fc, target_id, arr, join_id, append_only=False)



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




pts_df.index = pts_df.index.map(str) # <- didn't help
pts_df.index = pts_df.index.map(int) # <- didn't help
pts_df.index
pts_df, bws_trans = calc_beach_width(pts_df, maxDH, tID_fld) # still not working
