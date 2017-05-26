'''
Deep dive Transect Extraction for Fire Island, NY 2012
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 5/4/2016

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options, uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *
from TE_config_ParkerRiver2014 import *

start = time.clock()

"""
Pre-processing
"""

# Check presence of default files in gdb
extendedTrans = SetInputFCname(home, 'extendedTrans', extendedTrans)
i_name = SetInputFCname(home, 'inlets delineated (inletLines)', inletLines, system_ext=False)
armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)
bb_name = SetInputFCname(home, 'barrier island polygon (barrierBoundary)', barrierBoundary, False)
new_shore = SetInputFCname(home, 'shoreline between inlets', shoreline, False)
elevGrid_5m = SetInputFCname(home, 'DEM raster at 5m res (elevGrid_5m)', elevGrid_5m, False)
dhPts = SetInputFCname(home, 'dune crest points (dhPts)', dhPts)
dlPts = SetInputFCname(home, 'dune toe points (dlPts)', dlPts)
ShorelinePts = SetInputFCname(home, 'shoreline points (ShorelinePts)', ShorelinePts)

# DUNE POINTS
# Replace fill values with Null
ReplaceValueInFC(dhPts,["dhigh_z"])
ReplaceValueInFC(dlPts,["dlow_z"])
ReplaceValueInFC(ShorelinePts,["slope"])
# Populate ID with OID?

# INLETS
if not i_name:
    arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=arcpy.SpatialReference(proj_code))
    print("{} created. Now we'll stop for you to manually create lines at each inlet.")
    exit()
else:
    inletLines = i_name

# BOUNDARY POLYGON
if not bb_name:
    rawbarrierline = DEMtoFullShorelinePoly(elevGrid, '{site}{year}'.format(**SiteYear_strings), MTL, MHW, inletLines, ShorelinePts)
    # Eliminate any remnant polygons on oceanside
    if pythonaddins.MessageBox('Ready to delete selected features from {}?'.format(rawbarrierline),'',4) == 'Yes':
        arcpy.DeleteFeatures_management(rawbarrierline)
    else:
        print("Ok, redo.")
        exit()

    barrierBoundary = NewBNDpoly(rawbarrierline, ShorelinePts, barrierBoundary,'25 METERS','50 METERS')
else:
    barrierBoundary = bb_name

# SHORELINE
if not new_shore:
    shoreline = CreateShoreBetweenInlets(barrierBoundary,inletLines,shoreline,ShorelinePts,proj_code)
else:
    shoreline = new_shore

# TRANSECTS
# see TE_preprocessing.py
if not extendedTrans:
    CopyAndWipeFC(trans_orig, trans_presort)
    pythonaddins.MessageBox("Now we'll stop so you can copy existing groups of transects to fill in the gaps. If possible avoid overlapping transects", "Created {}. Proceed with manual processing.".format(trans_presort), 0)
    exit()
# Delete any NAT transects in the new transects layer
if not extendedTrans:
    arcpy.SelectLayerByLocation_management(trans_presort, "ARE_IDENTICAL_TO", trans_orig) # or "SHARE_A_LINE_SEGMENT_WITH"
    if int(arcpy.GetCount_management(trans_presort)[0]) > 0: # if there are old transects in new transects, delete them
        arcpy.DeleteFeatures_management(trans_presort)
    # Append relevant NAT transects to the new transects
    arcpy.SelectLayerByLocation_management(trans_orig, "INTERSECT", barrierBoundary)
    arcpy.Append_management(trans_orig, trans_presort)
    pythonaddins.MessageBox("Now we'll stop so you can check that the transects are ready to be sorted either from the bottom up or top down. ", "Stop for manual processing.".format(trans_presort), 0)
    exit()
if not extendedTrans:
    # Sort
    trans_sort_1, count1 = SpatialSort(trans_presort,trans_sort_1,"LR",reverse_order=False,sortfield="sort_ID")
    # Extend
    ExtendLine(trans_sort_1,extendedTrans,extendlength,proj_code)
    if len(arcpy.ListFields(extendedTrans,'OBJECTID*')) == 2:
        ReplaceFields(extendedTrans,{'OBJECTID':'OID@'})

# ELEVATION
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)

pythonaddins.MessageBox("Pre-processing completed. Continue with transect extraction?", "Continue?", 1)

DeleteTempFiles()

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
print "Should take just a few minutes"
startPart1 = time.clock()

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
arcpy.Sort_management(extendedTrans,extendedTransects,transUIDfield)
# Make sure transUIDfield counts from 1
with arcpy.da.SearchCursor(extendedTransects, transUIDfield) as cursor:
    row = next(cursor)

if row[0] > 1:
    offset = row[0]-1
    with arcpy.da.UpdateCursor(extendedTransects, transUIDfield) as cursor:
        for row in cursor:
            row[0] = row[0]-offset
            cursor.updateRow(row)

"""
shoreline and armor
# Make shoreline points using shoreline and ShorelinePts: intersection of shoreline with transects + slope from ShorelinePts
# Take intersection of transects with shoreline to replace ShL nulls
"""
arcpy.Intersect_analysis((shoreline,extendedTransects), shl2trans+'_temp', output_type='POINT')
AddXYAttributes(shl2trans+'_temp',shl2trans,'SL')

ReplaceFields(ShorelinePts,{'ID':'OID@'},'SINGLE')
arcpy.SpatialJoin_analysis(shl2trans,ShorelinePts, 'join_temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # one-to-one # Error could result from different coordinate systems?
arcpy.JoinField_management(shl2trans,transUIDfield,'join_temp',transUIDfield,'slope')
arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')

shlfields = ['SL_Lon','SL_Lat','SL_easting','SL_northing','Bslope']
arcpy.DeleteField_management(extendedTransects,shlfields) #In case of reprocessing
#fldsToDelete = [arcpy.ListFields(extendedTransects,'{}_1'.format(f)) for f in shlfields]
#[arcpy.DeleteField_management(extendedTransects,x[0].name) for x in fldsToDelete]
arcpy.JoinField_management(extendedTransects,transUIDfield,shl2trans,transUIDfield,shlfields)

if not arcpy.Exists(arm2trans):
    # Create armor points with XY and LatLon fields
    DeleteExtraFields(armorLines)
    arcpy.Intersect_analysis((armorLines,extendedTransects), tempfile, output_type='POINT')
    AddXYAttributes(tempfile,arm2trans,'Arm')
    # Get elevation at points
    if arcpy.Exists(elevGrid_5m):
        arcpy.sa.ExtractMultiValuesToPoints(arm2trans,elevGrid_5m) # this produced a Background Processing error: temporary solution is to disable background processing in the Geoprocessing Options
        arcpy.AlterField_management(arm2trans,elevGrid_5m,armz,armz)
    else:
        arcpy.AddField_management(arm2trans,armz)

armorfields = ['Arm_Lon','Arm_Lat','Arm_easting','Arm_northing','Arm_z']
arcpy.DeleteField_management(extendedTransects, armorfields) #In case of reprocessing
arcpy.JoinField_management(extendedTransects, transUIDfield, arm2trans, transUIDfield, armorfields)
# How do I know which point will be encountered first? - don't want those in back to take the place of

# Dune metrics
dhfields = {'DH_Lon':'lon', 'DH_Lat':'lat', 'DH_easting':'east', 'DH_northing':'north', 'DH_z':'dhigh_z'}
BeachPointMetricsToTransects(extendedTransects, dhPts, dh2trans, dhfields, joinfields=[transUIDfield,transUIDfield], firsttime=True, tempfile=tempfile, tolerance=pt2trans_disttolerance)
dlfields = {'DL_Lon':'lon', 'DL_Lat':'lat', 'DL_easting':'east', 'DL_northing':'north', 'DL_z':'dlow_z'}
tempfile = 'dl_trans_temp'
BeachPointMetricsToTransects(extendedTransects, dlPts, dl2trans, dlfields, joinfields=[transUIDfield,transUIDfield], firsttime=True, tempfile=tempfile, tolerance=pt2trans_disttolerance)

# Adjust DL, DH, and Arm height to MHW
heightfields = ['DL_z','DH_z','DL_zMHW', 'DH_zMHW','Arm_z','Arm_zMHW']
AddNewFields(extendedTransects,heightfields)
with arcpy.da.UpdateCursor(extendedTransects, heightfields) as cursor:
    flist = cursor.fields
    for row in cursor:
        try:
            row[flist.index('DL_zMHW')] = row[flist.index('DL_z')] + dMHW
        except:
            pass
        try:
            row[flist.index('DH_zMHW')] = row[flist.index('DH_z')] + dMHW
        except:
            pass
        try:
            row[flist.index('Arm_zMHW')] = row[flist.index('Arm_z')] + dMHW
        except:
            pass
        cursor.updateRow(row)


endPart1 = time.clock()
duration = endPart1 - startPart1
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 1 completed in %dh:%dm:%fs" % (hours, minutes, seconds)
'''____________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\              /\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////             /\\\///////\\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                 \///       \/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                          /\\\/
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                        /\\\//
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                     /\\\//
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                   /\\\/
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                  /\\\\\\\\\\\\\\\
          \///              \///        \///  \///        \///        \///                  \///////////////
______________________________________________________________________________________________________________
Calculate distances (beach height, beach width, beach slope, max elevation)
Requires: Shoreline points, clipped transects
'''

print "Starting part 4"
print 'Should be quick!'
startPart2 = time.clock()

"""
DistDH, DistDL, DistArm: Distance of dunes/armoring from MHW shoreline
"""
# Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
fieldlist = ["DistDH", "DistDL", "DistArm", "SL_easting", "SL_northing", "DH_easting", "DH_northing", "DL_easting", "DL_northing", "Arm_easting", "Arm_northing"]
AddNewFields(extendedTransects,fieldlist)

# ERROR below: 'operation was attempted on an empty geometry'
with arcpy.da.UpdateCursor(extendedTransects, fieldlist) as cursor:
    for row in cursor:
        try:
            sl_x = row[cursor.fields.index('SL_easting')]
            sl_y = row[cursor.fields.index('SL_northing')]
        except:
            pass
        try:
            row[cursor.fields.index('DistDH')] = hypot(sl_x - row[cursor.fields.index('DH_easting')], sl_y - row[cursor.fields.index('DH_northing')])
            #row[0] = math.sqrt((row[3] - row[5])**2 + (row[6] - row[4])**2) # alternative: hypot(sl_x - d_x, sl_y - d_y)
        except:
            pass
        try:
            row[cursor.fields.index('DistDL')] = hypot(sl_x - row[cursor.fields.index('DL_easting')], sl_y - row[cursor.fields.index('DL_northing')])
            #row[1] = math.sqrt((row[3] - row[7])**2 + (row[8] - row[4])**2)
        except:
            pass
        try:
            row[cursor.fields.index('DistArm')] = hypot(sl_x - row[cursor.fields.index('Arm_easting')], sl_y - row[cursor.fields.index('Arm_northing')])
            #row[2] = math.sqrt((row[3] - row[9])**2 + (row[10] - row[4])**2)
        except:
            pass
        cursor.updateRow(row)

# Calculate additional beach parameters
# Set fields that will be used to calculate beach width and store the results
# fields = ['DL_z','DH_z','Arm_z',
#           'DL_easting','DL_northing',
#           'DH_easting','DH_northing',
#           'Arm_easting','Arm_northing',
#           'Bslope',
#           'DistDH','DistDL','DistArm',
#           'SL_easting',
#           'SL_northing',
fields = ['MLW_easting',
          'MLW_northing',
          'beach_h_MHW',
          'beachWidth_MHW',
          'beach_h_MLW',
          'beachWidth_MLW',
          'Source_beachwidth',
          'CP_easting','CP_northing', # Ben's label for easting and northing of dune point (DL,DH,or DArm) to be used for beachWidth and beach_h_MHW
          'CP_zMHW']
distfields = ['DistDH','DistDL','DistArm'] # distance from shoreline

# Add fields if they don't already exist
#AddNewFields(baseName,'Source_beachwidth','TEXT')
AddNewFields(extendedTransects,fields)

# Calculate
errorct = 0
transectct = 0
with arcpy.da.UpdateCursor(extendedTransects,'*') as cursor:
    for row in cursor:
        transectct +=1
        # Find which of DL, DH, and Arm is closest to MHW and not Null (exclude DH if higher than maxDH)
        cp = FindNearestPointWithZvalue(row,cursor.fields,distfields,maxDH) # prefix of closest point metric
        if cp: # if closest point was found calculate beach width with that point, otherwise skip
            # Calculate beach width = Euclidean distance from dune (DL, DH, or Arm) to MHW and MLW
            # Set values from each row
            d_x = row[cursor.fields.index(cp+'_easting')]
            d_y = row[cursor.fields.index(cp+'_northing')]
            b_slope = row[cursor.fields.index('Bslope')]
            sl_x = row[cursor.fields.index('SL_easting')]
            sl_y = row[cursor.fields.index('SL_northing')]
            #beachWidth_MHW = CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y)
            mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_MLW(oMLW,d_x,d_y,b_slope,sl_x,sl_y)
            beach_h_MHW = row[cursor.fields.index(cp+'_zMHW')]
            # update Row values
            row[cursor.fields.index('MLW_easting')] = mlw_x
            row[cursor.fields.index('MLW_northing')] = mlw_y
            row[cursor.fields.index('beach_h_MHW')] = beach_h_MHW
            row[cursor.fields.index('beachWidth_MHW')] = row[cursor.fields.index('Dist'+cp)]
            row[cursor.fields.index('beach_h_MLW')] = beach_h_MHW-oMLW
            row[cursor.fields.index('beachWidth_MLW')] = beachWidth_MLW
            #row[cursor.fields.index('Source_beachwidth')] = cp
            row[cursor.fields.index('CP_easting')] = row[cursor.fields.index(cp+'_easting')]
            row[cursor.fields.index('CP_northing')] = row[cursor.fields.index(cp+'_northing')]
            row[cursor.fields.index('CP_zMHW')] = row[cursor.fields.index(cp+'_zMHW')]
            # update Row values
            cursor.updateRow(row)
        else:
            errorct +=1
            pass

# Report
print "Beach Width could not be calculated for {} out of {} transects.".format(errorct,transectct)

# Create MLW and CP points for error checking
arcpy.MakeXYEventLayer_management(extendedTransects,'MLW_easting','MLW_northing',MLWpts+'_lyr',utmSR)
arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)
arcpy.MakeXYEventLayer_management(extendedTransects,'CP_easting','CP_northing',CPpts+'_lyr',utmSR)
arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)

endPart2 = time.clock()
duration = endPart2 - startPart2
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)


'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\      /\\\\\\\\\\\\\\\             /\\\\\\\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\  \///////\\\/////             \//////////////\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\        \/\\\                              \/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/         \/\\\                       /\\\\\\\\\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\         \/\\\                      \/////////\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\        \/\\\                              \/\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\       \/\\\                   /\\\       \/\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\      \/\\\                  \//\\\\\\\\\\\\/
          \///              \///        \///  \///        \///       \///                   \/////////////
______________________________________________________________________________________________________________
Create Transect Segment points and sample data
Requires: clipped transects with shoreline fields
'''
print "Starting Part 3"
startPart3 = time.clock()
"""
Dist2Inlet: Calc dist from inlets
# Requires transects and shoreline
"""
Dist2Inlet(extendedTransects, shoreline, transUIDfield, xpts='xpts_temp')

"""
AddNewFields(extendedTransects,'Dist2Inlet')

# Measure distance from inlet to each transect in both directions
arcpy.Intersect_analysis([extendedTransects,shoreline],'xptsroute_temp','ALL','1 METERS','POINT')
# Convert shoreline to routes
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT') # Check that the inlet is southwest of the study area
#arcpy.Intersect_analysis([extendedTransects,'shore_routeLL_temp'],'xptsroute_temp','ALL','1 METERS','POINT') # Intersect on route instead of plain line creates Multipoint M shape instead of Multipoint
# Make DistTableLL - distance from each transect to southwest inlet
arcpy.LocateFeaturesAlongRoutes_lr('xptsroute_temp',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
# Add MEAS (distance from southwest inlet to transect) to FC
arcpy.DeleteField_management(extendedTransects, "MEAS") # in case of reprocessing
arcpy.JoinField_management(extendedTransects, transUIDfield, 'DistTableLL',transUIDfield, "MEAS")

arcpy.MakeFeatureLayer_management(shoreline,shoreline+'_lyr','"Join_Count">1') # Only use sections that intersect two inlet lines
arcpy.CreateRoutes_lr(shoreline+'_lyr',"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
# pull in intersect points
arcpy.LocateFeaturesAlongRoutes_lr('xptsroute_temp',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.JoinField_management(extendedTransects, transUIDfield, 'DistTableUR',transUIDfield, "MEAS")
# Save lowest *non-Null* distance value as Dist2Inlet
with arcpy.da.UpdateCursor(extendedTransects, ('Dist2Inlet', 'MEAS', 'MEAS_1')) as cursor:
    for row in cursor:
        if isinstance(row[1],float) and isinstance(row[2],float):
            row[0] = min(row[1], row[2])
        elif not isinstance(row[1],float):
            row[0] = row[2]
        else:
            row[0] = row[1]
        cursor.updateRow(row)

# Tidy up
arcpy.DeleteField_management(extendedTransects, "MEAS")
arcpy.DeleteField_management(extendedTransects, "MEAS_1")
"""
DeleteTempFiles()

endPart3 = time.clock()
duration = endPart3 - startPart3
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 4 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''______________________________________________________________________________________________________________

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
Clip transects, get barrier widths
Requires: extended transects, boundary polygon
'''

print "Starting Part 4"
startPart4 = time.clock()

"""
Island width - total land (WidthLand), farthest sides (WidthFull), and segment (WidthPart)
"""
# ALTERNATIVE: add start_x, start_y, end_x, end_y to baseName and then calculate Euclidean distance from array
#arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xptsbarrier_temp',output_type='POINT') # ~40 seconds
#arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xlinebarrier_temp',output_type='LINE') # ~30 seconds
#arcpy.CreateRoutes_lr(extendedTransects,transUIDfield,"transroute_temp","LENGTH")
# find farthest point to sl_x, sl_y => WidthFull and closest point => WidthPart

# Clip transects with boundary polygon
arcpy.Clip_analysis(extendedTransects, barrierBoundary, baseName) # ~30 seconds

# WidthLand
ReplaceFields(baseName,{'WidthLand':'SHAPE@LENGTH'})

# WidthFull
#arcpy.CreateRoutes_lr(extendedTransects,transUIDfield,"transroute_temp","LENGTH",ignore_gaps="NO_IGNORE") # for WidthFull
# Create simplified line for full barrier width that ignores interior bays: verts_temp > trans_temp > length_temp
arcpy.FeatureVerticesToPoints_management(baseName, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect # ~20 seconds
arcpy.PointsToLine_management("verts_temp","trans_temp",transUIDfield) # creates trans_temp: clipped transects with single vertices # ~1 min
arcpy.SimplifyLine_cartography("trans_temp", "length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP") # creates length_temp: removes extraneous bends while preserving essential shape; adds InLine_FID and SimLnFlag; # ~2 min 20 seconds
ReplaceFields("length_temp",{'WidthFull':'SHAPE@LENGTH'})
# Join clipped transects with full barrier lines and transfer width value
arcpy.JoinField_management(baseName, transUIDfield, "length_temp", transUIDfield, "WidthFull")

# Calc WidthPart as length of the part of the clipped transect that intersects MHW_oceanside
arcpy.MultipartToSinglepart_management(baseName,'singlepart_temp')
ReplaceFields("singlepart_temp",{'WidthPart':'SHAPE@LENGTH'})
arcpy.SelectLayerByLocation_management('singlepart_temp', "INTERSECT", shoreline, '10 METERS')
arcpy.JoinField_management(baseName,transUIDfield,"singlepart_temp",transUIDfield,"WidthPart")

# Save final transects before moving on to segmenting them
arcpy.DeleteField_management(extendedTransects, ["WidthFull","WidthLand","WidthPart"]) # in case of reprocessing
arcpy.JoinField_management(extendedTransects,transUIDfield,baseName,transUIDfield,["WidthFull","WidthLand","WidthPart"])
print "Final population of " + extendedTransects + " completed. "
arcpy.FeatureClassToFeatureClass_conversion(extendedTransects,home,transects_final)
print "Creation of " + transects_final + " completed. "

# Remove temp files
DeleteTempFiles()

endPart4 = time.clock()
duration = endPart4 - startPart4
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)




'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\      /\\\\\\\\\\\\\\\             /\\\\\\\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\  \///////\\\/////             \/\\\///////////
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\        \/\\\                  \/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/         \/\\\                  \/\\\\\\\\\\\\\\
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
print 'Expect a 3 to 15 minute wait'
startPart5 = time.clock()

# Select the boundary lines between groups of overlapping transects
arcpy.CopyFeatures_management(baseName,overlapTrans_lines)
arcpy.SelectLayerByAttribute_management(baseName, "CLEAR_SELECTION")
arcpy.Intersect_analysis([baseName,overlapTrans_lines],trans_x,'ALL',output_type="POINT")
arcpy.SplitLineAtPoint_management(baseName,trans_x,trans_noOver)

arcpy.SelectLayerByLocation_management(trans_noOver, "INTERSECT", shoreline, '10 METERS',invert_spatial_relationship='INVERT')
arcpy.DeleteFeatures_management(trans_noOver)

baseName = trans_noOver

"""
# Split transects into segments
"""
# Convert transects to 5m points: multi to single; split lines; segments to center points
#arcpy.MultipartToSinglepart_management(baseName, tranSplitPts+'Sing_temp')
input1 = os.path.join(home,tranSplitPts+'Sing_temp')
output = os.path.join(home, tranSplitPts+'Split_temp')
arcpy.MultipartToSinglepart_management(baseName, input1)
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx")
arcpy.XToolsGP_SplitPolylines_xtp(input1,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
transPts_presort = tranSplitPts+'Presort_temp'
arcpy.FeatureToPoint_management(tranSplitPts+'Split_temp',transPts_presort)

"""
# Calculate distance of point from shoreline and dunes (Dist_Seg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
# Requires fields: SL_easting, SL_northing, WidthPart, seg_x, seg_y
Could be replaced by raster processing...
"""
ReplaceFields(transPts_presort,{'seg_x':'SHAPE@X','seg_y':'SHAPE@Y'}) # Add xy for each segment center point
arcpy.AddField_management(transPts_presort,"Dist_Seg","DOUBLE")   # distance from MHW oceanside
arcpy.AddField_management(transPts_presort,"Dist_MHWbay","DOUBLE") # distance from MHW bayside
with arcpy.da.UpdateCursor(transPts_presort, ['Dist_Seg','Dist_MHWbay','seg_x','seg_y','SL_easting','SL_northing','WidthPart']) as cursor:
    for row in cursor:
        try:
            row[0] = dist2mhw = math.sqrt((row[2] -row[4])**2 + (row[3] - row[5])**2) # hypot(row[4]-row[2],row[5]-row[3])
            row[1] = row[6] - dist2mhw
        except:
            pass
        cursor.updateRow(row)

# Sort on transUIDfield and DistSeg (id_temp)
RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, tranSplitPts, [[transUIDfield,'ASCENDING'],['Dist_Seg','ASCENDING']])
ReplaceFields(tranSplitPts,{'SplitSort':'OID@'})

# Calculate DistSeg* = distance of point from *
# Requires fields: DistDH, DistDL, DistArm, Dist_Seg
distfields = ['DistSegDH','DistSegDL','Dist_Seg','DistDH','DistDL','DistArm','DistSegArm']
AddNewFields(tranSplitPts, distfields)
with arcpy.da.UpdateCursor(tranSplitPts, distfields) as cursor:
    for row in cursor:
        flist = cursor.fields
        try:
            row[flist.index('DistSegDH')] = row[flist.index('Dist_Seg')]-row[flist.index('DistDH')]
        except:
            pass
        try:
            row[flist.index('DistSegDL')] = row[flist.index('Dist_Seg')]-row[flist.index('DistDL')]
        except:
            pass
        try:
            row[flist.index('DistSegArm')] = row[flist.index('Dist_Seg')]-row[flist.index('DistArm')]
        except:
            pass
        cursor.updateRow(row)

# Tidy up
arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID"])
DeleteTempFiles()

# Report time
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

print "Starting Part 6"
print "Expect ~ minutes to extract values from points"

# Extract elevation and slope at points and calculate average elevation per transect
# Requires: tranSplitPts (points at which to extract elevation), elevGrid

# Create slope grid if doesn't already exist
if not arcpy.Exists(slopeGrid):
    arcpy.Slope_3d(elevGrid_5m,slopeGrid,'PERCENT_RISE')

#Get elevation and slope at points ### TAKES A WHILE?
if arcpy.Exists(pts_elevslope):
    # Join elevation and slope values from a previous iteration of the script
    arcpy.JoinField_management(tranSplitPts,"SplitSort",pts_elevslope,"SplitSort",['PointZ','PointZ_mhw','PointSlp'])
else:
    arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,[[elevGrid_5m,'PointZ'],[slopeGrid,'PointSlp']])
    AddNewFields(tranSplitPts, 'PointZ_mhw')
    with arcpy.da.UpdateCursor(tranSplitPts,['PointZ','PointZ_mhw']) as cursor:
        for row in cursor:
            try:
                row[1] = row[0] - MHW
            except:
                pass
            cursor.updateRow(row)

    arcpy.CopyFeatures_management(tranSplitPts,pts_elevslope)

"""
# Get max_Z and mean_Z for each transect
"""
# save max and mean in out_stats table using Statistics_analysis
out_stats = "avgZ_byTransect"
arcpy.Statistics_analysis(tranSplitPts,out_stats,
    [['PointZ_mhw','MAX'],['PointZ_mhw','MEAN'],['PointZ_mhw','COUNT']],transUIDfield)
# remove mean values if fewer than 80% of 5m points had elevation values
with arcpy.da.UpdateCursor(out_stats,['*']) as cursor:
    for row in cursor:
        if row[cursor.fields.index('COUNT_PointZ_mhw')]/row[cursor.fields.index('FREQUENCY')] <= 0.8:
            row[cursor.fields.index('MEAN_PointZ_mhw')] = None
            cursor.updateRow(row)

# add mean and max fields to points FC using JoinField_management
arcpy.JoinField_management(tranSplitPts,transUIDfield,out_stats,transUIDfield,['MAX_PointZ_mhw','MEAN_PointZ_mhw']) # very slow ~1 hr for Monomoy

"""
Save final files
"""
# Save pts as feature class with Nulls (transSplitPts_final)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts,home,tranSplitPts_null)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts,home,tranSplitPts_fill)
ReplaceValueInFC(tranSplitPts_fill,[], None, fill)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts_fill,out_dir,tranSplitPts_shp+'.shp')
arcpy.TableToTable_conversion(tranSplitPts_fill, out_dir, tranSplitPts_fill+'.csv')

finalmessage = "The final products ("+tranSplitPts_shp+") were exported as a shapefile and CSV to "+out_dir+". \n" \
      "\nNow enter the USER to save the table: \n\n" \
      "1. Open the CSV in Excel and then Save as... a .xlsx file. \n" \
      "2. Open the XLS file in Matlab with the data checking script to check for errors! "
print finalmessage
pythonaddins.MessageBox(finalmessage, 'Final Steps')


end = time.clock()
duration = end - start
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "\nProcessing completed in %dh:%dm:%fs" % (hours, minutes, seconds)
