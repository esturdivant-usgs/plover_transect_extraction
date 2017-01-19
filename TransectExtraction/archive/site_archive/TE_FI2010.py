'''
Deep dive Transect Extraction for Fire Island, NY 2012
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 2/26/2016

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options, uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''

import arcpy, time, os, pythonaddins, sys
#import collections
#from math import radians, cos, asin, sin, atan2, sqrt, degrees, hypot
#from operator import add
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
#arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
############ Inputs #########################

arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\FireIsland2010.gdb"

year = '2010'
site = 'FI'

# Site-specific values
MLW = -1.01 						# MLW offset from MHW # Beach height adjustment (relative to MHW)
dMHW = -.46

AskUserToSelectInputs = False        # User selects each input feature class at beginning of process
if not AskUserToSelectInputs:
    fillValuesInPts = True              # If True, -99999 fill values in dune points will be replaced with None
    deletePtsWithZfill = False           # If True, dune points with elevations of fill (-99999) will be deleted
    OceansideLineTooLong = True  # 'short', 'long', or False
    ElevResolutionIs1m = False           # If True, reprojects (mean Aggregate) to 5m resolution
    CreateMHWline = False
    MeasureDistFromBothSides = True

dhPts = site+year+'_DHpts_edit1'				# Dune crest
dlPts = site+year+'_DLpts_edit1' 				# Dune toe
ShorelinePts = site+year+'_SLpts_edit1projected'    # Shoreline points, MUST BE PROJECTED
MHW_oceanside = site+year+"_FullShoreline"
inletLines = site+year+'_inletLines'             # manually create lines based on the boundary polygon that correspond to end of land and cross the MHW line
armorLines = site+year+'_sandfencing'
extendedTransects = site+"_extTransects_v2_sorted" # Created MANUALLY: see TransExtv4Notes.txt
barrierBoundary = site+year+'_BNDpoly_MHWocean'   # Barrier Boundary polygon; create with TE_createBoundaryPolygon.py
elevGrid = site+year+'_DEM_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat
rawtransects = False
rawbarrierline = 'LI_BND_2012Line'

start = time.clock()

"""
'''____________________________________________________________________________________________________________

   /\\\\\\\\\\\\  /\\\      /\\\  /\\\    /\\\
   \/\\\////////  \/\\\     \/\\\ \/\\\\  \/\\\
    \/\\\          \/\\\     \/\\\ \/\\\\\ \/\\\
     \/\\\\\\\\\\\\ \/\\\     \/\\\ \/\\\\\\\/\\\
      \/\\\////////  \/\\\     \/\\\ \/\\\ \\\/\\\
       \/\\\          \/\\\     \/\\\ \/\\\ \\\\\\\
        \/\\\          \/\\\_____\/\\\ \/\\\  \\\\\\
         \/\\\          \/\\\\\\\\\\\/  \/\\\   \\\\\
          \///             \/////////    \///    ////
______________________________________________________________________________________________________________
'''

# General use functions
def SetInputFCname(workingdir, varname, inFCname):
    if arcpy.Exists(inFCname):
        inFCname = inFCname
    else:
        inFCname = pythonaddins.OpenDialog("Select "+varname+" File (e.g. "+inFCname+")", False, workingdir,'Select')
        if inFCname:
            inFCname = os.path.basename(inFCname)
        else:
            inFCname = False
            print
    return inFCname
def fieldExists(inFeatureClass, inFieldName):
   fieldList = arcpy.ListFields(inFeatureClass)
   for iField in fieldList:
      if iField.name.lower() == inFieldName.lower():
         return True
   return False
def ReplaceFields(fc,newoldfields,fieldtype='DOUBLE'):
    # Use tokens to save geometry properties as attributes
    # E.g. newoldfields={'LENGTH':'SHAPE@LENGTH'}
    for (new, old) in newoldfields.items():
        if fieldExists(fc,new):
            try:
                arcpy.DeleteField_management(fc,new)
            except:
                pass
        arcpy.AddField_management(fc,new,fieldtype)
        with arcpy.da.UpdateCursor(fc,[new, old]) as cursor:
            for row in cursor:
                row[0] = row[1]
                cursor.updateRow(row)
        if fieldExists(fc,old):
            try:
                arcpy.DeleteField_management(fc,old)
            except:
                print arcpy.GetMessage(2)
                pass
def AddXYAttributes(fc,newfc,prefix):
    newoldfields = {prefix+'_northing':'SHAPE@Y',prefix+'_easting':'SHAPE@X'}
    ReplaceFields(fc,newoldfields)
    nad83 = arcpy.SpatialReference(4269)
    arcpy.Project_management(fc,newfc,nad83) # Works manually, but sometimes not in code
    newoldfields = {prefix+'_Lat':'SHAPE@Y',prefix+'_Lon':'SHAPE@X'}
    ReplaceFields(newfc,newoldfields)
    arcpy.Delete_management(fc)
def ReplaceValueInFC(fc,fields=[],oldvalue=-99999,newvalue=None):
    # Replace oldvalue with newvalue in fields in fc
    if len(fields) < 1:
        fs = arcpy.ListFields(fc)
        for f in fs:
            fields.append(f.name)
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            for i in range(len(fields)):
                if row[i] == oldvalue:
                    row[i] = newvalue
            cursor.updateRow(row)
def DeleteFeaturesByValue(fc,fields=[], deletevalue=-99999):
    if len(fields) < 1:
        fs = arcpy.ListFields(fc)
        for f in fs:
            fields.append(f.name)
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            for i in range(len(fields)):
                if row[i] == deletevalue:
                    cursor.deleteRow()

# Part 1 functions
def ExtendLine(lyrname,distance):
    # From GIS stack exchange http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance
    # layer must have map projection
    def newcoord(coords, dist):
        # Computes new coordinates x3,y3 at a specified distance along the prolongation of the line from x1,y1 to x2,y2
        (x1,y1),(x2,y2) = coords
        dx = x2 - x1
        dy = y2 - y1
        linelen = hypot(dx, dy)

        x3 = x2 + dx/linelen * dist
        y3 = y2 + dy/linelen * dist
        return x3, y3
    def accumulate(iterable):
        # accumulate([1,2,3,4,5]) --> 1 3 6 10 15
        # Equivalent to itertools.accumulate() which isn't present in Python 2.7
        it = iter(iterable)
        total = next(it)
        yield total
        for element in it:
            total = add(total, element)
            yield total
    # Will use OID to determine how to break up flat list of data by feature.
    coordinates = [[row[0], row[1]] for row in arcpy.da.SearchCursor(lyrname, ["OID@", "SHAPE@XY"], explode_to_points=True)]
    oid,vert = zip(*coordinates)
    # Construct list of numbers that mark the start of a new feature class by counting OIDS and accumulating the values.
    vertcounts = list(accumulate(collections.Counter(oid).values()))
    #Grab the last two vertices of each feature
    lastpoint = [point for x,point in enumerate(vert) if x+1 in vertcounts or x+2 in vertcounts]
    # Obtain list of tuples of new end coordinates by converting flat list of tuples to list of lists of tuples.
    distance = float(distance)
    newvert = [newcoord(y, distance) for y in zip(*[iter(lastpoint)]*2)]
    j = 0
    with arcpy.da.UpdateCursor(lyrname, "SHAPE@XY", explode_to_points=True) as rows:
        for i,row in enumerate(rows):
            if i+1 in vertcounts:
                row[0] = newvert[j]
                j+=1
                rows.updateRow(row)
def JoinMetricsToTransects(transects,tempfile,fieldnamesdict):
    # Add fields from tempfile to transects
    for new in fieldnamesdict.keys():
        if fieldExists(transects,new):
            try:
                arcpy.DeleteField_management(transects,new)
            except:
                pass
    arcpy.JoinField_management(transects, "OBJECTID", tempfile, "FID_"+transects, fieldnamesdict.values())
    # Rename new fields
    for (new,old) in fieldnamesdict.items():
        try:
            arcpy.AlterField_management(transects,old,new,new)
        except:
            pass
    arcpy.Delete_management(os.path.join(home,tempfile))
def JoinFieldsByTransOrder(fc,sourcefile,joinfieldsdict,joinfields=['TransOrder','TransOrder']):
        # Add fields from tempfile to transects
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
        arcpy.Delete_management(os.path.join(home,sourcefile))
def BeachPointMetricsToTransects(transects, oldPts, newPts, fieldnamesdict, firsttime=True, tempfile='trans_temp', tolerance='25 METERS'):
    # Save only points within 10m of transect and join beach point metrics to transects
    # 1. Create ID field and populate with OBJECTID
    # 2. Join nearest point within 10m to transect --> tempfile
    if firsttime:
        #PointsToTransOrder(transects,oldPts,newPts,tempfile)
        ReplaceFields(oldPts,{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(transects,oldPts, tempfile,'#','#','#',"CLOSEST",tolerance) # one-to-one # Error could result from different coordinate systems?
    if newPts: # Is this condition necessary?
        if not arcpy.Exists(newPts):
            arcpy.AddJoin_management(oldPts,"ID", tempfile,"ID","KEEP_COMMON") # KEEP COMMON is the key to this whole thing - probably a better way to accomplish with SelectByLocation...
            arcpy.CopyFeatures_management(oldPts, newPts)
            arcpy.RemoveJoin_management(oldPts)
    # Delete any fields with raw suffix to prevent confusion with lat lon east north fields that we want to use
    try:
        for fname in arcpy.ListFields(transects,'*_raw'):
            arcpy.DeleteField_management(transects,fname)
    except:
        pass
    JoinFieldsByTransOrder(transects,tempfile,fieldnamesdict)

# Part 4 functions
def FindFieldWithMinValue(row,fielddict,fieldlist):
    vdict = dict()
    for f in fieldlist:
        v = row[fielddict[f]]
        if v == None:
            pass
        else:
            vdict[v] = f
    vsorted = sorted(vdict.items(), key=lambda x: (x is None, x)) # this doesn't work
    cp = []
    for i in range(len(vsorted)):
        cp.append(vsorted[i][1])
    return cp
def FindNearestPointWithZvalue(row,fielddict,fieldlist):
    cps = FindFieldWithMinValue(row,fielddict,fieldlist)
    if len(cps)>0:
        i = 0
        while i < len(cps):
            cp = cps[i][4:]
            if (row[fielddict[cp+'_z']] is None): # or (cp == 'DH' and (row[dict1[cp+'_z']] > maxDH)):
                cp = None
                i = i+1
            elif cp == 'DH' and (row[dict1[cp+'_z']] > maxDH):
                cp = None
                i = i+1
            else:
                i = len(cps)+1
    else:
        cp = None
    return cp
def CalcBeachWidthGeometry(MLW,dune_lon,dune_lat,beach_z,beach_slope,SL_Lon,SL_Lat):
    # Calculate beach width based on dune and shoreline coordinates, beach height and slope, and MLW adjustment value
    try:
        beach_h_MLW = beach_z - MLW
        delta_xm_MLW = abs(beach_h_MLW/beach_slope) # Euclidean distance between dune and MLW # Bslope replaces sin of slope # Bslope was pulled in from shoreline points

        # 3 Convert chord distance to Angular distance along great circle (gc)
        mlwKM = delta_xm_MLW/1000
        r = 6371 # Radius of earth in meters
        delta_x_gc_MLW = d2 = 2 * asin(mlwKM/(2*r))

        # 4 Find Azimuth between dune and MHW shoreline
        dlon = radians(SL_Lon - dune_lon)
        dlat = radians(SL_Lat - dune_lat)
        lon1 = radians(dune_lon)
        lat1 = radians(dune_lat)
        lon2 = radians(SL_Lon)
        lat2 = radians(SL_Lat)

        x = sin(dlon) * cos(lat2)
        y = (cos(lat1) * sin(lat2)) - (sin(lat1) * cos(lat2) * cos(dlon))
        theta = atan2(x,y)
        if degrees(theta) < 0:
            azimuth_SL = degrees(theta)+360
        else:
            azimuth_SL = degrees(theta)
        phiR = radians(azimuth_SL)

        # 5 Calculate Position of MLW shoreline based on azimuth # Replace SL position with MLW position # SL is MHW so MHW is replaced by MLW through complex geometry calculations
        latMLW = lat2 = asin((sin(lat2) * cos(d2)) + (cos(lat2) * sin(d2) * cos(phiR)))
        lonMLW = lon2 = lon2 + atan2(sin(phiR)*sin(d2)*cos(lat2), cos(d2)-sin(lat2)*sin(latMLW))
        MLW_Lat = degrees(latMLW)
        MLW_Lon = degrees(lonMLW)

        # 6 Calculate beach width from dune to MLW shoreline
        dlon = radians(MLW_Lon - dune_lon)
        dlat = radians(MLW_Lat - dune_lat)
        a = (sin(dlat/2) * sin(dlat/2)) + (cos(lat1) * cos(lat2) * (sin(dlon/2) * sin(dlon/2)))
        c = 2 * atan2(sqrt(a), sqrt(1-a)) # Angular distance in radians
        dMLW = r * c  # Distance (m) between dune and MLW
        beachWidth_MLW = dMLW*1000

        output = [beach_h_MLW, delta_xm_MLW, azimuth_SL, MLW_Lat, MLW_Lon, beachWidth_MLW]
    except TypeError:
        output = [None, None, None, None, None, None]
    return output
"""

########### Default Values ##########################
fill = -99999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
nad83utm18 = arcpy.SpatialReference(26918)
extendlength = 2000                      # extended transects distance (m) IF NEEDED

############## Outputs ###############################
dh2trans = '{}{}_DH2trans'.format(site,year)							# DHigh within 10m
dl2trans = site+year+'_DL2trans'						# DLow within 10m
arm2trans = site+year+'_arm2trans'
arm2transZ = site+year+'_arm2trans_withZ'
shl2trans = site+year+'_SHL2trans'							# beach slope from lidar within 10m of transect
MLWpts = site+year+'_MLW2trans'                       # MLW points calculated during Beach Width calculation
shoreline = site+year+'_ShoreBetweenInlets'        # Complete shoreline ready to become route in Pt. 2
slopeGrid = site+year+'_slope5m'
baseName = 'trans_clip_working'                     # Clipped transects
transects_part2 = site+year+'_transpart2'
transects_final = site+year+'_populatedTransects'
transSplitPts_final = site+year+'_trans_5mPts'
tempfile = 'trans_temp'
armz = 'Arm_z'
tranSin = site+year+'_trans_SinglePart' 				# Single part transects
tranSplit = site+year+'_trans_5mSeg' 			# Transect Segments (5m)
tranSplitPts = site+'_trans_5mSegPts' 	# Outputs Transect Segment points
transPts_presort = 'trans_5m_segpts_presort_temp'
pts_elevslope = tranSplitPts+'_ZSlp'

# Check presence of default files in gdb
if AskUserToSelectInputs:
    dhPts = SetInputFCname(home, 'dune crest points (dhPts)', dhPts)
    dlPts = SetInputFCname(home, 'dune toe points (dlPts)', dlPts)
    ShorelinePts = SetInputFCname(home, 'shoreline points (ShorelinePts)', ShorelinePts)
    ans = pythonaddins.MessageBox('Dune metric points have fill values (not Nulls)?', 'Dune metrics',4) #False  # If True, -99999 fill values in dune points will be replaced with None
    fillValuesInPts=True if ans=='Yes' else False
    ans = pythonaddins.MessageBox('Delete points with fill Z values?', 'Dune metrics',4) #False           # If True, dune points with elevations of fill (-99999) will be deleted
    deletePtsWithZfill=True if ans=='Yes' else False

    MHW_oceanside = SetInputFCname(home, 'oceanside MHW line (MHW_oceanside)', MHW_oceanside)
    CreateMHWline=True if not MHW_oceanside else False

    ans=pythonaddins.MessageBox('Is MHW line longer than the boundary and therefore needs to be trimmed?','Shoreline',4)
    OceansideLineTooLong=True if ans=='Yes' else False

    inletLines = SetInputFCname(home, 'inlet lines (inletLines)', inletLines)
    armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)
    extendedTransects = SetInputFCname(home, 'extendedTransects', extendedTransects)

    barrierBoundary = SetInputFCname(home, 'barrier island polygon (barrierBoundary)', barrierBoundary)
    rawbarrierline = SetInputFCname(home, 'barrier island line (rawbarrierline)', rawbarrierline) if not barrierBoundary else False

    elevGrid = SetInputFCname(home, 'DEM raster (elevGrid)', elevGrid)
    ans=pythonaddins.MessageBox('Is the resolution of the DEM raster 1m?','Raster resolution',4) # If True, reprojects (mean Aggregate) to 5m resolution
    ElevResolutionIs1m=True if ans=='Yes' else False



'''____________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\                 \\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////             /\\\\\\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                 \/////\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                     \/\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                     \/\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                     \/\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                     \/\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                     \/\\\
          \///              \///        \///  \///        \///        \///                      \///
______________________________________________________________________________________________________________
Create Extended transects, DH & DL points within 10m of transects
Requires DH, DL, and SHL points, NA transects
'''
print "Starting Part 1"
startPart1 = time.clock()

# Extend transects if not already
if not arcpy.Exists(extendedTransects):
    if not rawtransects:
        rawtransects = SetInputFCname(home, 'Raw transects', 'rawtransects')
    arcpy.Project_management(rawtransects,extendedTransects,nad83utm18)
    ExtendLine(extendedTransects,extendlength)
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

#### PRE-PROCESS DUNE POINT METRICS #####
# Delete points with fill Z values - indicates that Ben&Rob disqualified them from analysis
if deletePtsWithZfill:
    #arcpy.SelectLayerByAttribute_management(orig_dhPts,'NEW_SELECTION','dhigh_Z > %d' % fill)
    arcpy.CopyFeatures_management(orig_dhPts,dhPts)
    DeleteFeaturesByValue(dhPts,['dhigh_z'])
    #arcpy.SelectLayerByAttribute_management(orig_dlPts,'NEW_SELECTION','dlow_Z > %d' % fill)
    arcpy.CopyFeatures_management(orig_dlPts,dlPts)
    DeleteFeaturesByValue(dlPts,['dlow_z'])

# Replace fill values with Null and populate ID with OBJECTID
if fillValuesInPts:
    ReplaceValueInFC(dhPts,["dhigh_z"])
    ReplaceValueInFC(dlPts,["dlow_z"])
    ReplaceValueInFC(ShorelinePts,["slope"])

### CREATE MHW_oceanside from SLpts if needed ### MUST BE PROJECTED
if CreateMHWline:
    arcpy.PointsToLine_management(ShorelinePts, MHW_oceanside)

#### CREATE SHORELINE from MHW_oceanside ####
# MHW_oceanside must be projected to nad83utm18
"""
if not arcpy.Exists(shoreline):
    DeleteExtraFields(inletLines)
    if not OceansideLineTooLong:
        # Merge and then extend shoreline to inlet lines
        arcpy.Merge_management([MHW_oceanside,inletLines],shoreline)
        arcpy.ExtendLine_edit(shoreline,'250 Meters')
        arcpy.TrimLine_edit(shoreline, dangle_length="3100 Meters", delete_shorts="DELETE_SHORT") ### NEW = check
        # should delete extra lines, but if there is no bounding inlet on one side, that shoreline will also be deleted
    elif OceansideLineTooLong:
        # Create oceanside line = shoreline
        arcpy.Intersect_analysis([inletLines,MHW_oceanside],'xpts','ONLY_FID',output_type='POINT') # temp1_pts
        arcpy.SplitLineAtPoint_management(MHW_oceanside,'xpts','split_temp','1 Meters')
        # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
        arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", ShorelinePts,'1 METERS')
        arcpy.CopyFeatures_management('split_temp',shoreline)

        arcpy.Delete_management(os.path.join(home,'xpts'))
        arcpy.Delete_management(os.path.join(home,'split_temp'))
    else:
        pass
    ReplaceFields(shoreline,{'ORIG_FID':'OID@'},'SHORT')
else:
    pass
"""
if not arcpy.Exists(shoreline):
    DeleteExtraFields(inletLines)
    # Merge and then extend shoreline to inlet lines
    arcpy.Merge_management([MHW_oceanside,inletLines],'shore_temp')
    arcpy.ExtendLine_edit('shore_temp','250 Meters')
    arcpy.Intersect_analysis([inletLines,'shore_temp'],'xpts','ONLY_FID',output_type='POINT')
    arcpy.SplitLineAtPoint_management('shore_temp','xpts','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", ShorelinePts,'1 METERS') # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
    arcpy.SpatialJoin_analysis('split_temp',inletLines,shoreline,"JOIN_ONE_TO_ONE") # count intersecting inlet lines

    arcpy.Delete_management(os.path.join(home,'shore_temp'))
    arcpy.Delete_management(os.path.join(home,'xpts'))
    arcpy.Delete_management(os.path.join(home,'split_temp'))

    ReplaceFields(shoreline,{'ORIG_FID':'OID@'},'SHORT')
else:
    pass

##### shoreline and armoring #####
# Make shoreline points using shoreline and ShorelinePts
# intersection of shoreline with transects + slope from ShorelinePts
# Take intersection of transects with shoreline to replace ShL nulls
arcpy.Intersect_analysis((shoreline,extendedTransects), shl2trans+'_temp', output_type='POINT')
AddXYAttributes(shl2trans+'_temp',shl2trans,'SL')

ReplaceFields(ShorelinePts,{'ID':'OID@'},'SINGLE')
temp = arcpy.SpatialJoin_analysis(shl2trans,ShorelinePts, 'temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # one-to-one # Error could result from different coordinate systems?
arcpy.JoinField_management(shl2trans,'TRANSORDER',temp,'TRANSORDER','slope')
arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')

shlfields = ['SL_Lon','SL_Lat','SL_easting','SL_northing','Bslope']
arcpy.DeleteField_management(extendedTransects,shlfields) #In case of reprocessing
#fldsToDelete = [arcpy.ListFields(extendedTransects,'{}_1'.format(f)) for f in shlfields]
#[arcpy.DeleteField_management(extendedTransects,x[0].name) for x in fldsToDelete]
arcpy.JoinField_management(extendedTransects,"TRANSORDER",shl2trans,'TRANSORDER',shlfields)


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

if not arcpy.Exists(arm2transZ):
    # Create armor points with XY and LatLon fields
    DeleteExtraFields(armorLines)
    arcpy.Intersect_analysis((armorLines,extendedTransects), tempfile, output_type='POINT')
    AddXYAttributes(os.path.join(home,tempfile),arm2trans,'Arm')
    # Get elevation at points
    arcpy.MultipartToSinglepart_management(arm2trans,arm2transZ)
    if arcpy.Exists(elevGrid):
        arcpy.sa.ExtractMultiValuesToPoints(arm2transZ,elevGrid) # this produced a Background Processing error: temporary solution is to disable background processing in the Geoprocessing Options
        arcpy.AlterField_management(arm2transZ,elevGrid,armz,armz)
    else:
        arcpy.AddField_management(arm2transZ,armz)

armorfields = ['Arm_Lon','Arm_Lat','Arm_easting','Arm_northing','Arm_z']
arcpy.DeleteField_management(extendedTransects,armorfields) #In case of reprocessing
arcpy.JoinField_management(extendedTransects,"TRANSORDER",arm2transZ,'TRANSORDER',armorfields)

# Dune metrics
dhfields = {'DH_Lon':'lon', 'DH_Lat':'lat', 'DH_easting':'east', 'DH_northing':'north', 'DH_z':'dhigh_z'}
BeachPointMetricsToTransects(extendedTransects,dhPts,dh2trans,dhfields, True, tempfile, pt2trans_disttolerance)
dlfields = {'DL_Lon':'lon', 'DL_Lat':'lat', 'DL_easting':'east', 'DL_northing':'north', 'DL_z':'dlow_z'}
BeachPointMetricsToTransects(extendedTransects,dlPts,dl2trans,dlfields, True, tempfile, pt2trans_disttolerance)

# Adjust DL, DH, and Arm height to MHW
arcpy.AddField_management(extendedTransects, 'DL_zMHW', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_zMHW', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'Arm_zMHW', 'DOUBLE')
with arcpy.da.UpdateCursor(extendedTransects, ('DL_z','DH_z','DL_zMHW', 'DH_zMHW','Arm_z','Arm_zMHW')) as cursor:
    for row in cursor:
        try:
            row[2] = row[0] + dMHW
        except:
            pass
        try:
            row[3] = row[1] + dMHW
        except:
            pass
        try:
            row[5] = row[4] + dMHW
        except:
            pass
        cursor.updateRow(row)

endPart1 = time.clock()
duration = endPart1 - startPart1
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 1 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''______________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\              /\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////             /\\\///////\\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                 \///       \//\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                          /\\\/
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                        /\\\//
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                     /\\\//
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                   /\\\/
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                  /\\\\\\\\\\\\\\\
          \///              \///        \///  \///        \///        \///                  \///////////////
______________________________________________________________________________________________________________
Clip transects, get barrier widths, populate DH DL distances
Requires: extended transects, boundary polygon
'''
print "Starting Part 2"
startPart2 = time.clock()

if not arcpy.Exists(barrierBoundary):
    barrierBoundary = NewBNDpoly(rawbarrierline, MHW_oceanside, newbndname=barrierBoundary)

# Clip transects with boundary polygon
arcpy.Clip_analysis(extendedTransects, barrierBoundary, baseName)

# Island width - total land (WidthLand), farthest sides (WidthFull), and segment (WidthPart)
ReplaceFields(baseName,{'WidthLand':'SHAPE@LENGTH'})

# Create simplified line for full barrier width that ignores interior bays: verts_temp > trans_temp > length_temp
arcpy.FeatureVerticesToPoints_management(baseName, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect
arcpy.PointsToLine_management("verts_temp","trans_temp","TransOrder") # creates trans_temp: clipped transects with single vertices
arcpy.SimplifyLine_cartography("trans_temp", "length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP") # creates length_temp: removes extraneous bends while preserving essential shape; adds InLine_FID and SimLnFlag;
ReplaceFields("length_temp",{'WidthFull':'SHAPE@LENGTH'})
# Join clipped transects with full barrier lines and transfer width value
arcpy.JoinField_management(baseName, "TransOrder", "length_temp","TransOrder", "WidthFull")

# Calc WidthPart as length of the part of the clipped transect that intersects MHW_oceanside
arcpy.MultipartToSinglepart_management(baseName,'singlepart_temp')
ReplaceFields("singlepart_temp",{'WidthPart':'Shape_Length'})
arcpy.SelectLayerByLocation_management('singlepart_temp', "INTERSECT", MHW_oceanside, '10 METERS')
arcpy.JoinField_management(baseName,"TransOrder","singlepart_temp","TransOrder","WidthPart")

# Remove temp files
arcpy.Delete_management(os.path.join(home,"length_temp"))
arcpy.Delete_management(os.path.join(home,"trans_temp"))
arcpy.Delete_management(os.path.join(home,"verts_temp"))
arcpy.Delete_management(os.path.join(home,"singlepart_temp"))

# Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
fieldlist = ["DistDH","DistDL","DistArm","SL_easting","SL_northing","DH_easting","DH_northing","DL_easting","DL_northing","Arm_easting","Arm_northing"]
for newfname in fieldlist:
    if not fieldExists(baseName, newfname):
        arcpy.AddField_management(baseName, newfname, "DOUBLE")
        print 'Added '+newfname+' field to '+baseName
# ERROR below: 'operation was attempted on an empty geometry'
with arcpy.da.UpdateCursor(baseName, fieldlist) as cursor:
    for row in cursor:
        try:
            row[0] = math.sqrt((row[3] - row[5])**2 + (row[6] - row[4])**2)
        except:
            pass
        try:
            row[1] = math.sqrt((row[3] - row[7])**2 + (row[8] - row[4])**2)
        except:
            pass
        try:
            row[2] = math.sqrt((row[3] - row[9])**2 + (row[10] - row[4])**2)
        except:
            pass
        cursor.updateRow(row)

# Dist2Inlet: Calc dist from inlets
# Requires transects and shoreline
if not fieldExists(baseName,'Dist2Inlet'):
     arcpy.AddField_management(baseName, 'Dist2Inlet','DOUBLE')
"""
# Convert shoreline to routes # Measure distance from inlet to each transect in both directions
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT') # Check that the inlet is southwest of the study area
arcpy.Intersect_analysis([baseName,'shore_routeLL_temp'],'xpts','ALL','1 METERS','POINT')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.DeleteField_management(baseName, "MEAS") # in case of reprocessing
arcpy.JoinField_management(baseName, "TRANSORDER", 'DistTableLL',"TRANSORDER", "MEAS")


# Only measure distance from inlets indicated by inletLines

#cnt = arcpy.GetCount_management(shoreline)
if MeasureDistFromBothSides:
    arcpy.SelectLayerByAttribute_management(shoreline,"NEW_SELECTION",'"OBJECTID"<4') # <<< Specific to Fire Island
    arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
    arcpy.SelectLayerByAttribute_management(shoreline,"CLEAR_SELECTION")
    # pull in intersect points
    arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
    arcpy.JoinField_management(baseName, "TRANSORDER", 'DistTableUR',"TRANSORDER", "MEAS")
    # Save lowest *non-Null* distance value as Dist2Inlet
    with arcpy.da.UpdateCursor(baseName, ('Dist2Inlet', 'MEAS', 'MEAS_1')) as cursor:
        for row in cursor:
            if isinstance(row[1],float) and isinstance(row[2],float):
                row[0] = min(row[1], row[2])
            elif not isinstance(row[1],float):
                row[0] = row[2]
            else:
                row[0] = row[1]
            cursor.updateRow(row)
    arcpy.DeleteField_management(baseName, "MEAS_1")
    arcpy.Delete_management(os.path.join(home,"shore_routeUR_temp"))
    arcpy.Delete_management(os.path.join(home,"DistTableUR"))
else:
    with arcpy.da.UpdateCursor(baseName, ('Dist2Inlet', 'MEAS')) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
"""

# Convert shoreline to routes # Measure distance from inlet to each transect in both directions
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT') # Check that the inlet is southwest of the study area
arcpy.Intersect_analysis([baseName,'shore_routeLL_temp'],'xpts','ALL','1 METERS','POINT')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.DeleteField_management(baseName, "MEAS") # in case of reprocessing
arcpy.JoinField_management(baseName, "TRANSORDER", 'DistTableLL',"TRANSORDER", "MEAS")

arcpy.SelectLayerByAttribute_management(shoreline,"NEW_SELECTION",'"Join_Count">1') # Only use shoreline sections that intersects two inlet lines
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
arcpy.SelectLayerByAttribute_management(shoreline,"CLEAR_SELECTION")
# pull in intersect points
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.JoinField_management(baseName, "TRANSORDER", 'DistTableUR',"TRANSORDER", "MEAS")
# Save lowest *non-Null* distance value as Dist2Inlet
with arcpy.da.UpdateCursor(baseName, ('Dist2Inlet', 'MEAS', 'MEAS_1')) as cursor:
    for row in cursor:
        if isinstance(row[1],float) and isinstance(row[2],float):
            row[0] = min(row[1], row[2])
        elif not isinstance(row[1],float):
            row[0] = row[2]
        else:
            row[0] = row[1]
        cursor.updateRow(row)

# Tidy up
arcpy.DeleteField_management(baseName, "MEAS")
arcpy.DeleteField_management(baseName, "MEAS_1")
arcpy.Delete_management(os.path.join(home,"xpts"))
arcpy.Delete_management(os.path.join(home,"shore_routeLL_temp"))
arcpy.Delete_management(os.path.join(home,"shore_routeUR_temp"))
arcpy.Delete_management(os.path.join(home,"DistTableLL"))
arcpy.Delete_management(os.path.join(home,"DistTableUR"))

arcpy.CopyFeatures_management(baseName,transects_part2)

endPart2 = time.clock()
duration = endPart2 - startPart2
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)


'''____________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\                      /\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////                     /\\\\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                        /\\\/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                      /\\\/\/\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                    /\\\/  \/\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                  /\\\\\\\\\\\\\\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                 \///////////\\\//
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                           \/\\\
          \///              \///        \///  \///        \///        \///                            \///
______________________________________________________________________________________________________________
Populate Lidar Metrics (SL-shorelinePts,beach height, beach width, beach slope, max elevation)
Requires: Shoreline points, clipped transects
'''
print "Starting part 4"
startPart4 = time.clock()

# Calculate additional beach parameters
# Set fields that will be used to calculate beach width and store the results
fields = ['DL_z','DH_z','Arm_z',
          'DL_easting','DL_northing',
          'DH_easting','DH_northing',
          'Arm_easting','Arm_northing',
          'Bslope',
          'DistDH','DistDL','DistArm',
          'SL_easting',
          'SL_northing',
          'MLW_easting',
          'MLW_northing',
          'beach_h_MLW',
          'beachWidth_MLW',
          'Source_beachwidth']
distfields = ['DistDH','DistDL','DistArm']

# Add fields if don't already exist
if not fieldExists(baseName, 'Source_beachwidth'):
    arcpy.AddField_management(baseName, 'Source_beachwidth', "TEXT",3)
    print 'Added Source_beachwidth field to '+baseName
for newfname in fields:
    if not fieldExists(baseName, newfname):
        arcpy.AddField_management(baseName, newfname, "DOUBLE")
        print 'Added '+newfname+' field to '+baseName


# Calculate
errorct = 0
transectct = 0
with arcpy.da.UpdateCursor(baseName,'*') as cursor:
    for row in cursor:
        transectct +=1
        # Find which of DL, DH, and Arm is closest to SL and not Null
        cp = FindNearestPointWithZvalue(row,cursor.fields,distfields) # prefix of closest point metric
        if cp:
            # Set values from each row
            d_x = row[cursor.fields.index(cp+'_easting')]
            d_y = row[cursor.fields.index(cp+'_northing')]
            b_slope = row[cursor.fields.index('Bslope')]
            sl_x = row[cursor.fields.index('SL_easting')]
            sl_y = row[cursor.fields.index('SL_northing')]
            d_z = row[cursor.fields.index(cp+'_zMHW')]

            # Calculate beach height
            beach_h_MLW = d_z-MLW
            # Calculate beach width
            mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_v2(MLW,d_x,d_y,b_slope,sl_x,sl_y)

            # update Row values
            row[cursor.fields.index('MLW_easting')] = mlw_x
            row[cursor.fields.index('MLW_northing')] = mlw_y
            row[cursor.fields.index('beach_h_MLW')] = beach_h_MLW
            row[cursor.fields.index('beachWidth_MLW')] = beachWidth_MLW
            row[cursor.fields.index('Source_beachwidth')] = cp
            cursor.updateRow(row)
        else:
            errorct +=1
            pass
# Report
print "Beach Width could not be calculated for {} out of {} transects.".format(errorct,transectct)

# Create MLW points for error checking
arcpy.MakeXYEventLayer_management(baseName,'MLW_easting','MLW_northing',MLWpts+'_lyr',nad83utm18)
arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)


arcpy.CopyFeatures_management(baseName,transects_final)
# Replace null values with -99999 for final transects file, before segmenting
ReplaceValueInFC(transects_final,[],None,fill)

print "Creation of " + transects_final + " completed. "
#print "Creation of " + transects_final + " completed. Proceeding to create 5m segments and points."

endPart4 = time.clock()
duration = endPart4 - startPart4
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 4 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\      /\\\\\\\\\\\\\\\             /\\\\\\\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\  \///////\\\/////             \/\\\///////////
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\        \/\\\                  \/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/         \/\\\                  \/\\\\\\\\\\\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\         \/\\\                  \/////////////\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\        \/\\\                              \/\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\       \/\\\                   /\\\       \/\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\      \/\\\                  \//\\\\\\\\\\\\/
          \///              \///        \///  \///        \///       \///                   \/////////////
______________________________________________________________________________________________________________
Create Transect Segment points and sample data
Requires: clipped transects with shoreline fields
'''

print 'Starting Part 5'
startPart5 = time.clock()

# Split transects into segments
# Convert transects to 5m points: multi to single; split lines; segments to center points
arcpy.MultipartToSinglepart_management(baseName, tranSin)
input = home + '/' + tranSin
output = home + '/' + tranSplit
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx")
arcpy.XToolsGP_SplitPolylines_xtp(input,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
arcpy.FeatureToPoint_management(tranSplit,transPts_presort)

# Calc Dist_Seg field (dist of point from MHW oceanside)
# Requires fields: SL_easting, SL_northing, WidthPart
ReplaceFields(transPts_presort,{'seg_x':'SHAPE@X','seg_y':'SHAPE@Y'}) # Add xy for each segment center point
arcpy.AddField_management(transPts_presort,"Dist_Seg","DOUBLE")   # distance from MHW oceanside
arcpy.AddField_management(transPts_presort,"Dist_MHWbay","DOUBLE") # distance from MHW bayside
with arcpy.da.UpdateCursor(transPts_presort, ['Dist_Seg','Dist_MHWbay','seg_x','seg_y','SL_easting','SL_northing','WidthPart']) as cursor:
    for row in cursor:
        try:
            row[0] = dist2mhw = math.sqrt((row[2] -row[4])**2 + (row[3] - row[5])**2)
            row[1] = row[6] - dist2mhw
        except:
            pass
        cursor.updateRow(row)

# Create unique id SplitSort by sorting on TransOrder and DistSeg
arcpy.AddField_management(transPts_presort,"id_temp","TEXT")
#Create temp file with points sorted by [TRANSORDER]_[Dist_Seg] # Calc field - 24 seconds; cursor - 4.5 seconds
with arcpy.da.UpdateCursor(transPts_presort, ('TRANSORDER','Dist_Seg','id_temp')) as cursor:
    for row in cursor:
        try:
            dist = str(int(row[1]))
        except:
            dist = 'Null' # Must be Null string instead of None
        row[2] = "%s_%s" % (str(row[0]), dist)
        cursor.updateRow(row)

# Sort on TransOrder and DistSeg (id_temp)
arcpy.Sort_management(transPts_presort, tranSplitPts, 'TransOrder ASCENDING;Dist_Seg ASCENDING')
ReplaceFields(tranSplitPts,{'SplitSort':'OID@'})

# Calculate DistSegDH = distance of point from dune crest
# Requires fields: DistDH, DistDL, DistArm, Dist_Seg
arcpy.AddField_management(tranSplitPts,"DistSegDH","DOUBLE")
arcpy.AddField_management(tranSplitPts,"DistSegDL","DOUBLE")
arcpy.AddField_management(tranSplitPts,"DistSegArm","DOUBLE")
with arcpy.da.UpdateCursor(tranSplitPts, ('DistSegDH','DistSegDL','Dist_Seg','DistDH','DistDL','DistArm','DistSegArm')) as cursor:
    for row in cursor:
        try:
            row[0] = row[2]-row[3]
        except:
            pass
        try:
            row[1] = row[2]-row[4]
        except:
            pass
        try:
            row[6] = row[2]-row[5]
        except:
            pass
        cursor.updateRow(row)

arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID","id_temp"])
arcpy.Delete_management(home+'/'+ transPts_presort)

endPart5 = time.clock()
duration = endPart5 - startPart5
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 5 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\                   /\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////                  /\\\\/
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                     /\\\//
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                   /\\\\\\\\\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                  /\\\\///////\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                 \/\\\      \//\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                 \//\\\      /\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                  \///\\\\\\\\\/
          \///              \///        \///  \///        \///        \///                    \/////////
______________________________________________________________________________________________________________
Replace null values (for matlab)
Requires:  Segment Points, elevation, recharge, Habitat
'''
arcpy.AddMessage("Starting Part 6")

# Extract elevation and slope at points
# Requires: tranSplitPts (points at which to extract elevation), elevGrid
if ElevResolutionIs1m:
    outAggreg = arcpy.sa.Aggregate(elevGrid,5,'MEAN')
    elevGrid = elevGrid+'_5m'
    outAggreg.save(elevGrid)
# Create slope grid if doesn't already exist
if not arcpy.Exists(slopeGrid):
    arcpy.Slope_3d(elevGrid,slopeGrid,'PERCENT_RISE')

#Get elevation and slope at points ### TAKES A WHILE?
if arcpy.Exists(pts_elevslope):
    # Join elevation and slope values from a previous iteration of the script
    arcpy.JoinField_management(tranSplitPts,"SplitSort",pts_elevslope,"SplitSort",['PointZ','PointSlp'])
else:
    arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,[[elevGrid,'PointZ'],[slopeGrid,'PointSlp']])
    arcpy.CopyFeatures_management(tranSplitPts,pts_elevslope)

# Recharge and Habitat extract
"""
#Recharge
rechFields = ['zone','Rech','class']
arcpy.SpatialJoin_analysis(tranSplitPts,recharge,"rechargeJoin","JOIN_ONE_TO_ONE","KEEP_ALL") ### may take a while -> not too long

#assign new field names VegZone, VegRech, VegClass	and copy from join table
arcpy.JoinField_management(tranSplitPts,'SplitSort',"rechargeJoin",'SplitSort',rechFields) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"VegZone","SHORT")
arcpy.AddField_management(tranSplitPts,"VegRech","DOUBLE")
arcpy.AddField_management(tranSplitPts,"VegClass","TEXT")
arcpy.CalculateField_management(tranSplitPts, 'VegZone', '!zone!',"PYTHON")
arcpy.CalculateField_management(tranSplitPts, 'VegRech', '!Rech!',"PYTHON")
arcpy.CalculateField_management(tranSplitPts, 'VegClass', '!class!',"PYTHON")
arcpy.DeleteField_management(tranSplitPts,["zone","Rech",'class'])
arcpy.Delete_management("rechargeJoin")

#NPS habitat
habFields = ['Veg_Type']
arcpy.SpatialJoin_analysis(tranSplitPts,habitat,"habitatJoin","JOIN_ONE_TO_ONE","KEEP_ALL") ### may take a while -> not too long

#assign new field name HabNPS and copy from join table
arcpy.JoinField_management(tranSplitPts,'SplitSort',"habitatJoin",'SplitSort',habFields) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"HabNPS","TEXT")
arcpy.CalculateField_management(tranSplitPts, 'HabNPS', '!Veg_Type!',"PYTHON")
arcpy.DeleteField_management(tranSplitPts,'Veg_Type')
arcpy.Delete_management("habitatJoin")

#Transect average Recharge
#arcpy.Intersect_analysis('Transects_North_MorphVariables_050812 #;Recharge_modNov18_subset #', r'F:\ASIS\TransectPopulation_v2\Tools\Testing_gdb.gdb\trans_rech_temp', 'ALL', '#', 'INPUT')
#arcpy.DeleteField_management('trans_rech_temp', 'FID_Transects_North_MorphVariables_050812;WidthFull;WidthLand;percBeach;percSF;percWet;percUnk;DistToCana;LRR;beach_h;beach_w;toe_dl_z;crest_dh_z;slp_sh_slo;Start_lon;Start_lat;max_z;Nourish;D_B_Constr;OldInlet;Infrastr;DistDH;DistDL;Shape_Length_1;FID_Recharge_modNov18_subset;row;column_;zone;Rech;Conc;Depth')
"""


#arcpy.CopyFeatures_management(tranSplitPts,transSplitPts_final)
arcpy.MakeTableView_management(tranSplitPts,transSplitPts_final)
ReplaceValueInFC(transSplitPts_final,[], None, fill)

finalmessage = "\nNow enter the USER: \n\n" \
      "1. Export the new table ("+transSplitPts_final+") as Text with a '.csv' extension. \n" \
      "    Right click on the new table ("+transSplitPts_final+") in the Table of Contents. \n" \
      "2. Open the CSV in Excel and then Save as... a .xlsx file. \n" \
      "3. Finally, open the XLS file in Matlab with the data checking script to check for errors! "
print finalmessage
pythonaddins.MessageBox(finalmessage, 'Final Steps')


end = time.clock()
duration = end - start
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "\nProcessing completed in %dh:%dm:%fs" % (hours, minutes, seconds)
