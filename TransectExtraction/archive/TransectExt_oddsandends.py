"""
Sandbox for Deep dive Transect Extraction
Newer items are at the top
"""

import arcpy, time, os, pythonaddins, collections
from math import radians, cos, asin, sin, atan2, sqrt, degrees, hypot
from operator import add


arcpy.env.workspace= home= r"\\Mac\Home\Documents\ArcGIS\Default.gdb"

SiteYear_strings = {'site': 'Cobb',
                    'year': '2014',
                    'region': 'Virginia'}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(
    **SiteYear_strings)

min = 105
max = 131
with arcpy.UpdateCursor('Cobb_extTrans',['TransOrder']) as cursor:
    for row in cursor:
        if row[0] > min and row[0] < max:
            if row[0]%2==0:
                cursor.deleteRow(row)



# Inlet lines
if not arcpy.Exists(extendedTransects):
    if not rawtransects:
        rawtransects = SetInputFCname(home, 'Raw transects', 'rawtransects')
    ExtendLine(rawtransects,extendedTransects,extendlength,projection_code)
    if len(arcpy.ListFields(extendedTransects,'OBJECTID*')) == 2:
        ReplaceFields(extendedTransects,{'OBJECTID':'OID@'})

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
transwork = extendedTransects + '_' + year
arcpy.Sort_management(extendedTransects,transwork,'TRANSORDER')
extendedTransects = transwork
# Make sure TRANSORDER counts from 1
with arcpy.da.SearchCursor(extendedTransects, 'TRANSORDER') as cursor:
    row = next(cursor)
if row[0] > 1:
    offset = row[0]-1
    with arcpy.da.UpdateCursor(extendedTransects, 'TRANSORDER') as cursor:
        for row in cursor:
            row[0] = row[0]-offset
            cursor.updateRow(row)



"""
errorct = 0
successct = 0
with arcpy.da.UpdateCursor("trans_clip_working",['DistDL','SL_easting','SL_northing','DL_easting','DL_northing']) as cursor:
    for row in cursor:
        try:
            row[0] = math.sqrt((row[1] - row[3])**2 + (row[4] - row[2])**2)
            successct +=1
        except:
            errorct += 1
            pass
        cursor.updateRow(row)

arcpy.JoinField_management(tranSplitPts,"SplitSort",pts_elevslope,"SplitSort",['PointZ','PointSlp'])
"""

# OCEANSIDE SHORELINE
MHW_oceanside = SetInputFCname(home, 'oceanside MHW line (MHW_oceanside)', MHW_oceanside)
if not MHW_oceanside or CreateMHWline:
    # Create from SLpts or MHW_oceanside if needed
    MHW_oceanside = oceanside_auto
    #ShorelinePts = ReProject(ShorelinePts,ShorelinePts+'_utm',26918)

def CreateShoreBetweenInlets(SLpts,inletLines,out_line,proj_code=26918):
    # Create shoreline from shoreline points and inlet lines
    arcpy.PointsToLine_management(SLpts, 'line_temp')

    # Ready layers for processing
    DeleteExtraFields(inletLines)
    DeleteExtraFields('line_temp')
    line_temp = ReProject('line_temp','line_temp'+'_utm',proj_code)

    # Merge and then extend shoreline to inlet lines
    arcpy.Merge_management([line_temp,inletLines],'shore_temp')
    arcpy.ExtendLine_edit('shore_temp','500 Meters')

    # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
    arcpy.Intersect_analysis([inletLines,'shore_temp'],'xpts_temp','ONLY_FID',output_type='POINT')
    arcpy.SplitLineAtPoint_management('shore_temp','xpts_temp','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", SLpts,'1 METERS')

    # count intersecting inlet lines
    arcpy.SpatialJoin_analysis('split_temp',inletLines,out_line,"JOIN_ONE_TO_ONE")

    ReplaceFields(SLpts,{'ORIG_FID':'OID@'},'SHORT')
    return out_line



# Beach Point Metrics
"""

#def JoinFieldsByTransOrder(fc,sourcefile,joinfieldsdict,joinfields=['TransOrder','TransOrder']):


#def BeachPointMetricsToTransects(transects, oldPts, newPts, fieldnamesdict,firsttime=True, tempfile='trans_temp', tolerance='25 METERS'):
    # Save only points within 10m of transect and join beach point metrics to transects
    # 1. Create ID field and populate with OBJECTID
    # 2. Join nearest point within 10m to transect --> tempfile
if firsttime:
    #PointsToTransOrder(transects,oldPts,newPts,tempfile)
    ReplaceFields(oldPts,{'ID':'OID@'},'SINGLE')
# join attributes of closest dune point to transect --> tempfile
arcpy.SpatialJoin_analysis(transects,oldPts, tempfile,'#','#','#',"CLOSEST",tolerance) # one-to-one # Error could result from different coordinate systems?
# Create point fc by joining tempfile back to original points while only keeping common features
if not arcpy.Exists(newPts):
    arcpy.MakeFeatureLayer_management(oldPts,oldPts+'_lyr')
    arcpy.AddJoin_management(oldPts+'_lyr',"ID", tempfile,"ID","KEEP_COMMON") # KEEP COMMON is the key to this whole thing - probably a better way to accomplish with SelectByLocation...
    arcpy.CopyFeatures_management(oldPts+'_lyr', newPts)
    #arcpy.RemoveJoin_management(oldPts+'_lyr')
# Delete any fields with raw suffix to prevent confusion with lat lon east north fields that we want to use
try:
    for fname in arcpy.ListFields(transects,'*_raw'):
        arcpy.DeleteField_management(transects,fname)
except:
    pass

#JoinFieldsByTransOrder(transects,tempfile,fieldnamesdict)
for (new,old) in joinfieldsdict.items():
    if fieldExists(fc,new):
        try:
            arcpy.DeleteField_management(fc,new)
        except:
            pass
    if not fieldExists(sourcefile,old):
        # identify most similarly named field and replace in joinfieldsdict
        fieldlist = arcpy.ListFields(sourcefile,old+'*')
        if len(fieldlist) < 2:
            joinfieldsdict[new]=fieldlist[0].name
if len(joinfields)==1:
    arcpy.JoinField_management(fc, joinfields, sourcefile, joinfields, joinfieldsdict.values())
elif len(joinfields)==2:
    arcpy.JoinField_management(fc, joinfields[0], sourcefile, joinfields[1], joinfieldsdict.values())
else:
    print 'joinfield accepts either one or two values only.'
# Rename new fields
for (new,old) in joinfieldsdict.items():
    try:
        arcpy.AlterField_management(fc,old,new,new)
    except:
        pass
#arcpy.Delete_management(os.path.join(arcpy.env.workspace,sourcefile))
return fc
return transects


"""


"""
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,[[elevGrid_5m,'PointZ'],[slopeGrid,'PointSlp']])
arcpy.CopyFeatures_management(tranSplitPts,pts_elevslope)

# Extract elevation and slope values for FI 2012 and 2014
arcpy.env.workspace= r"\\Mac\Home\Documents\ArcGIS\FireIsland2014.gdb"
arcpy.sa.ExtractMultiValuesToPoints("FI2014_trans_5mPts_working",[["FI2014_lidar1m_5m",'PointZ'],["FI2014_slope5m",'PointSlp']])
arcpy.CopyFeatures_management("FI2014_trans_5mPts_working",pts_elevslope)

tranSplitPts="FI2014_trans_5mPts_working"
with arcpy.da.UpdateCursor(tranSplitPts,['PointZ','PointSlp','PointZ_1','PointSlp_1']) as cursor:
    for row in cursor:
        cursor.updateRow([row[2], row[3], row[2], row[3]])


joinfields = ["Dist2Inlet","DistArm","DistDH","DistDL","DistSegArm","DistSegDH","DistSegDL","MLW_easting",
              "MLW_northing","Dist_MHWbay","Dist_Seg","SL_Lat","SL_Lon","SL_easting","SL_northing","beach_h_MLW","beachWidth_MLW","Source_beachwidth"]


arcpy.JoinField_management(tranSplitPts,"TRANSORDER",extendedTransects,"TRANSORDER",'Dist2Inlet')
with arcpy.da.UpdateCursor(tranSplitPts,['Dist2Inlet','Dist2Inlet_1']) as cursor:
    for row in cursor:
        row[0]=row[1]
        cursor.updateRow(row)





arcpy.AddField_management(pts_elevslope,'beach_h_MLW','DOUBLE')
with arcpy.da.UpdateCursor(pts_elevslope,'*') as cursor:
    for row in cursor:
        cp = row[cursor.fields.index('Source_beachwidth')]
        if cp:
            zMHW = row[cursor.fields.index(cp+'_zMHW')]
            row[cursor.fields.index('beach_h_MLW')] = zMHW - MLW
        cursor.updateRow(row)
"""

# Shoreline coordinate join to transects
# alternate: (only use intersect points when there is no slope value at that shoreline point)
"""
arcpy.Intersect_analysis((shoreline,extendedTransects), shl2trans+'_temp', output_type='POINT')
AddXYAttributes(shl2trans+'_temp',shl2trans,'SLx')
ReplaceFields(ShorelinePts,{'ID':'OID@'},'SINGLE')
AddXYAttributes(ShorelinePts,ShorelinePts+'latlon','ShL')
temp = arcpy.SpatialJoin_analysis(shl2trans,ShorelinePts, 'temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # one-to-one # Error could result from different coordinate systems?
arcpy.JoinField_management(shl2trans,'TRANSORDER',temp,'TRANSORDER','slope')
with arcpy.da.UpdateCursor(shl2trans,)


shlfields = ['SL_Lon','SL_Lat','SL_easting','SL_northing','Bslope']
{arcpy.DeleteField_management(extendedTransects,field) for field in shlfields} #In case of reprocessing

arcpy.JoinField_management(extendedTransects,"TRANSORDER",shl2trans,'TRANSORDER',shlfields)
"""


# Mid-script validation:
"""
# Does field exist?
# Is it populated?
# Are the values within an expected range?
fc =
expectedrange =
fieldlist =
for newfield in fieldlist:
    if not fieldExists(fc,newfield):
        message = newfield+' not present in '+fc
        pythonaddins.MessageBox(message, 'Warning', 6)
        fieldlist.remove(newfield)
with arcpy.da.SearchCursor(fc,fieldlist) as cursor:
    for row in cursor:
        # record values, count nulls, etc.
    # get summary stats of recorded values and compare to expected...
"""

# 3/1
inputlist = [dhPts,dlPts,ShorelinePts,MHW_oceanside,inletLines,armorLines,extendedTransects,barrierBoundary,elevGrid]

# 2/26

# Delete features from DH and DL fcs that have fills for z-valu

# 2/24/16: Shoreline for Breezy Point
"""
# Current version (applied for Fire Island):
if arcpy.Exists(shoreline) == 0:
    # Create oceanside line that begins at jetty (canalPt) = 'shoreline'
    arcpy.Intersect_analysis([inletLines,MHW_oceanside],'xpts_createroute','ONLY_FID','POINT')
    arcpy.SplitLineAtPoint_management(MHW_oceanside,'xpts_createroute','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", ShorelinePts,'1 METERS')
    arcpy.CopyFeatures_management('split_temp',shoreline)
    ReplaceFields(shoreline,{'ORIG_FID':'OID@'},'SHORT')

    #arcpy.MultipartToSinglepart_management("split_temp", "Ocean_split_temp_singlepart")
    #arcpy.Select_analysis('Ocean_split_temp_singlepart',shoreline+'_temp','Shape_Length >0.01')

    # Eliminate bayside line, if it is present (does MHW_oceanside need to include bayside shore in current version?) based on presence of SHLpts
    #arcpy.SelectLayerByLocation_management(shoreline+'_temp',"INTERSECT", ShorelinePts)
    #arcpy.CopyFeatures_management('split_temp',shoreline)


    # Merge and then extend shoreline to inlet lines
    arcpy.Merge_management([shoreline+'_temp',inletLines],shoreline)
    arcpy.ExtendLine_edit(shoreline,'250 Meters')
    arcpy.TrimLine_edit(shoreline, dangle_length="3100 Meters", delete_shorts="DELETE_SHORT") ### NEW = check

    # Remove temp files
    arcpy.Delete_management(os.path.join(home,'xpts_createroute'))
    arcpy.Delete_management(os.path.join(home,'split_temp'))
else:
    pass

    # Extend shoreline beyond end of boundary polygon because end of polygon is not equivalent to inlet
    arcpy.AddField_management(shoreline+'_temp', 'LENGTH', 'LONG')
    arcpy.SelectLayerByAttribute_management("ShoreBetweenInlets_2014_temp","NEW_SELECTION",'"OBJECTID"=4')
    arcpy.CalculateField_management(shoreline+'_temp', "LENGTH", 80000, "Python_9.3")
    arcpy.BearingDistanceToLine_management(shoreline+'_temp', shoreline, "StartX", "StartY", "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))


# Previous version (BZpt_2014_withPart5v2)
if arcpy.Exists(shoreline) == 0:
    # Create oceanside line that begins at jetty (canalPt) = 'shoreline'
    arcpy.Select_analysis(baseName,'trans_canalline_temp','OBJECTID=1')
    arcpy.Intersect_analysis(['trans_canalline_temp',MHW_oceanside],'trans_canalpt_temp',"ONLY_FID",'1 METERS','POINT')
    arcpy.SplitLineAtPoint_management(MHW_oceanside,'trans_canalpt_temp','Ocean_split_temp','1 Meters')

    arcpy.MultipartToSinglepart_management("Ocean_split_temp", "Ocean_split_temp_singlepart")
    arcpy.Sort_management('Ocean_split_temp_singlepart','ocean_split_sorted_temp','Shape','UR')
    arcpy.Select_analysis('ocean_split_sorted_temp','shoreline_temp','OBJECTID=1')  # can't be condensed with below: eliminate additional segments that prevent line from extending
    # Merge all line to same feature class
    arcpy.Merge_management(['shoreline_temp',jetty_line,finalinlet],shoreline)
    arcpy.ExtendLine_edit(shoreline,'250 Meters')
    arcpy.TrimLine_edit(shoreline, dangle_length="3100 Meters", delete_shorts="DELETE_SHORT") ### NEW = check
    #arcpy.Sort_management('shoreline_jetty_merge','shorejetty_sorted','Shape','UR')
    #arcpy.Select_analysis('shorejetty_sorted',shoreline,'OBJECTID=1')
    # Remove temp files
    arcpy.Delete_management(os.path.join(home,'trans_canalline_temp'))
    arcpy.Delete_management(os.path.join(home,'trans_canalpt_temp'))
    arcpy.Delete_management(os.path.join(home,'Ocean_split_temp'))
    arcpy.Delete_management(os.path.join(home,'Ocean_split_temp_singlepart'))
    arcpy.Delete_management(os.path.join(home,'ocean_split_sorted_temp'))
    arcpy.Delete_management(os.path.join(home,'shoreline_temp'))
    #arcpy.Delete_management('shorejetty_sorted')
else:
    pass
"""

# Middle inlet distance calculation
"""
# Calc dist from canal
# Create shoreline if it does not already exist
inletLines = 'FI_inletLines'
MHW_oceanside = 'FireIsland_MHWline_2012v3'

arcpy.Intersect_analysis([inletLines,MHW_oceanside],'trans_canalpts_temp','ONLY_FID','1 METERS','POINT') # temp1_pts
arcpy.SplitLineAtPoint_management(MHW_oceanside,'trans_canalpts_temp','Ocean_split_temp','1 Meters')
arcpy.MultipartToSinglepart_management("Ocean_split_temp", "Ocean_split_temp_singlepart")
arcpy.Select_analysis('Ocean_split_temp_singlepart',shoreline,'Shape_Length >0.01')
# Remove temp files
arcpy.Delete_management(os.path.join(home,'trans_canalline_temp'))
arcpy.Delete_management(os.path.join(home,'trans_canalpts_temp'))
arcpy.Delete_management(os.path.join(home,'Ocean_split_temp'))
arcpy.Delete_management(os.path.join(home,'Ocean_split_temp_singlepart'))
# Calc distance from inlet using Linear Referencing toolbox
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT')
arcpy.Intersect_analysis([baseName,'shoreline_route_temp'],'xpts','ONLY_FID','1 METERS','POINT')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.JoinField_management(baseName, "OBJECTID", 'DistTableUR',"FID_"+baseName, "MEAS")
arcpy.JoinField_management(baseName, "OBJECTID", 'DistTableLL',"FID_"+baseName, "MEAS")
arcpy.AddField_management(baseName, "Dist2Inlet",'DOUBLE')
arcpy.CalculateField_management(baseName, "Dist2Inlet","min([!MEAS!,!MEAS_1!])", "PYTHON")
arcpy.CalculateField_management(baseName,'Dist2Inlet',)
arcpy.DeleteField_management(baseName, "MEAS")
arcpy.DeleteField_management(baseName, "MEAS_1")
"""

