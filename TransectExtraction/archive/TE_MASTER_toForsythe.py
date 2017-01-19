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
from TE_config import *


# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
# mxd = arcpy.mapping.MapDocument("CURRENT")
# df = arcpy.mapping.ListDataFrames(mxd)[0]
#arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
############ Inputs #########################
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2012',
                    'region': 'NewJersey',
                    'MHW':0.43,
                    'MLW':-0.61}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(
    **SiteYear_strings)
out_dir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)

deletePtsWithZfill = False          # If True, dune points with elevations of fill (-99999) will be deleted
CreateMHWline = False
rawtransects = False
rawbarrierline = 'LI_BND_2012Line'
transUIDfieldname = "trans_sort"

########### Automatic population ###########
MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
extendedTransects = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt
ShorelinePts = '{site}{year}_SLpts'.format(**SiteYear_strings)
dhPts = '{site}{year}_DHpts'.format(**SiteYear_strings)				# Dune crest
dlPts = '{site}{year}_DLpts'.format(**SiteYear_strings) 				# Dune toe
MHW_oceanside = "{site}{year}_MHWfromSLPs".format(**SiteYear_strings)
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)             # manually create lines based on the boundary polygon that correspond to end of land and cross the MHW line
armorLines = '{site}{year}_armor'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_bndpoly_2sl'.format(**SiteYear_strings)   # Barrier Boundary polygon; create with TE_createBoundaryPolygon.py
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)				# Elevation
elevGrid_5m = elevGrid+'_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat

########### Default Values ##########################
dMHW = -MHW                    # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
MTL = MHW-(MLW/2)
fill = -99999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
extendlength = 3000                      # extended transects distance (m) IF NEEDED
if SiteYear_strings['region'] == 'Massachusetts' or SiteYear_strings['region'] == 'RhodeIsland' or SiteYear_strings['region'] == 'Maine':
    proj_code = 26919 # "NAD 1983 UTM Zone 19N"
    utmSR = arcpy.SpatialReference(proj_code)
else:
    proj_code = 26918 # "NAD 1983 UTM Zone 18N"
    utmSR = arcpy.SpatialReference(proj_code)

############## Outputs ###############################
dh2trans = '{site}{year}_DH2trans'.format(**SiteYear_strings)							# DHigh within 10m
dl2trans = '{site}{year}_DL2trans'.format(**SiteYear_strings)						# DLow within 10m
arm2trans = '{site}{year}_arm2trans'.format(**SiteYear_strings)
oceanside_auto = '{site}{year}_MHWfromSLPs'.format(**SiteYear_strings)
shl2trans = '{site}{year}_SHL2trans'.format(**SiteYear_strings)							# beach slope from lidar within 10m of transect
MLWpts = '{site}{year}_MLW2trans'.format(**SiteYear_strings)                     # MLW points calculated during Beach Width calculation
shoreline = '{site}{year}_ShoreBetweenInlets'.format(**SiteYear_strings)        # Complete shoreline ready to become route in Pt. 2
slopeGrid = '{site}{year}_slope5m'.format(**SiteYear_strings)
baseName = 'trans_clip_working'                    # Clipped transects
transects_part2 = os.path.join(home,'trans_part2')
transects_final = '{site}{year}_trans_populated'.format(**SiteYear_strings)
tranSplitPts = '{site}{year}_transPts_working'.format(**SiteYear_strings) 	# Outputs Transect Segment points
tranSplitPts_null = '{site}{year}_transPts_null'.format(**SiteYear_strings)
tranSplitPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)
tranSplitPts_shp = '{site}{year}_transPts_shp'.format(**SiteYear_strings)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')

tempfile = 'trans_temp'
armz = 'Arm_z'


start = time.clock()

# Check presence of default files in gdb
extendedTransects = SetInputFCname(home, 'extendedTransects', extendedTransects)
i_name = SetInputFCname(home, 'inlets delineated (inletLines)', inletLines, False)
armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)
bb_name = SetInputFCname(home, 'barrier island polygon (barrierBoundary)', barrierBoundary, False)
new_shore = SetInputFCname(home, 'shoreline between inlets', shoreline, False)
elevGrid_5m = SetInputFCname(home, 'DEM raster at 5m res (elevGrid_5m)', elevGrid_5m, False)

"""
# DUNE POINTS
#### PRE-PROCESS DUNE POINT METRICS #####
"""
# Delete points with fill Z values - indicates that Ben&Rob disqualified them from analysis
dhPts = SetInputFCname(home, 'dune crest points (dhPts)', dhPts)
dlPts = SetInputFCname(home, 'dune toe points (dlPts)', dlPts)
ShorelinePts = SetInputFCname(home, 'shoreline points (ShorelinePts)', ShorelinePts)

if deletePtsWithZfill:
    ans = pythonaddins.MessageBox('Are you sure you want to delete points with fill Z values?', 'Dune metrics',4)
    # If True, dune points with elevations of fill (-99999) will be deleted
    deletePtsWithZfill=True if ans=='Yes' else False
if deletePtsWithZfill:
    arcpy.CopyFeatures_management(dhPts,dhPts+'_orig')
    DeleteFeaturesByValue(dhPts,['dhigh_z'])
    arcpy.CopyFeatures_management(dlPts,dlPts+'_orig')
    DeleteFeaturesByValue(dlPts,['dlow_z'])
# Replace fill values with Null
ReplaceValueInFC(dhPts,["dhigh_z"])
ReplaceValueInFC(dlPts,["dlow_z"])
ReplaceValueInFC(ShorelinePts,["slope"])
# Populate ID with OID?

# INLETS
if not i_name:
    arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=arcpy.SpatialReference(proj_code))
else:
    inletLines = i_name

# BOUNDARY POLYGON
if not bb_name:
    rawbarrierline = DEMtoFullShorelinePoly(elevGrid, '{site}{year}'.format(**SiteYear_strings), MTL, MHW, inletLines, ShorelinePts)
    # Eliminate any remnant polygons on oceanside
    if pythonaddins.MessageBox('Ready to delete selected features?','',4) == 'Yes':
        arcpy.DeleteFeatures_management(rawbarrierline)
    else:
        print 'Ok, redo.'
        exit()
    barrierBoundary = NewBNDpoly(rawbarrierline, ShorelinePts, barrierBoundary,'25 METERS','50 METERS')
else:
    barrierBoundary = bb_name

# SHORELINE
if not new_shore:
    shoreline = CreateShoreBetweenInlets(barrierBoundary,inletLines,shoreline,ShorelinePts,proj_code)
else:
    shoreline = new_shore

# ELEVATION
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)
    # check that resolution is 1m x 1m
    # desc = arcpy.Describe(elevGrid).spatialReference
    # prop = arcpy.GetRasterProperties_management(elevGrid, "CELLSIZEX")
    # if desc.PCSCode != proj_code or cs.getOutput(0) != '1':
    #     elevGrid2 = elevGrid+'_projected'
    #     arcpy.ProjectRaster_management(elevGrid, elevGrid2, utmSR,cell_size="1")
    # else:
    #     elevGrid2 = elevGrid
    # outAggreg = arcpy.sa.Aggregate(elevGrid2,5,'MEAN')
    # outAggreg.save(elevGrid_5m)
    #RemoveLayerFromMXD(outAggreg)

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

# Extend transects if not already
if not arcpy.Exists(extendedTransects):
    if not rawtransects:
        rawtransects = SetInputFCname(home, 'Raw transects', 'rawtransects')
    ExtendLine(rawtransects,extendedTransects,extendlength,projection_code)
    if len(arcpy.ListFields(extendedTransects,'OBJECTID*')) == 2:
        ReplaceFields(extendedTransects,{'OBJECTID':'OID@'})

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
transwork = extendedTransects + '_working'
arcpy.Sort_management(extendedTransects,transwork,transUIDfieldname)
extendedTransects = transwork
# Make sure transUIDfieldname counts from 1
with arcpy.da.SearchCursor(extendedTransects, transUIDfieldname) as cursor:
    row = next(cursor)
if row[0] > 1:
    offset = row[0]-1
    with arcpy.da.UpdateCursor(extendedTransects, transUIDfieldname) as cursor:
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
arcpy.JoinField_management(shl2trans,transUIDfieldname,'join_temp',transUIDfieldname,'slope')
arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')

shlfields = ['SL_Lon','SL_Lat','SL_easting','SL_northing','Bslope']
arcpy.DeleteField_management(extendedTransects,shlfields) #In case of reprocessing
#fldsToDelete = [arcpy.ListFields(extendedTransects,'{}_1'.format(f)) for f in shlfields]
#[arcpy.DeleteField_management(extendedTransects,x[0].name) for x in fldsToDelete]
arcpy.JoinField_management(extendedTransects,transUIDfieldname,shl2trans,transUIDfieldname,shlfields)

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
arcpy.JoinField_management(extendedTransects, transUIDfieldname, arm2trans, transUIDfieldname, armorfields)
# How do I know which point will be encountered first? - don't want those in back to take the place of

# Dune metrics
dhfields = {'DH_Lon':'lon', 'DH_Lat':'lat', 'DH_easting':'east', 'DH_northing':'north', 'DH_z':'dhigh_z'}
BeachPointMetricsToTransects(extendedTransects, dhPts, dh2trans, dhfields, True, tempfile, pt2trans_disttolerance)
dlfields = {'DL_Lon':'lon', 'DL_Lat':'lat', 'DL_easting':'east', 'DL_northing':'north', 'DL_z':'dlow_z'}
BeachPointMetricsToTransects(extendedTransects, dlPts, dl2trans, dlfields, True, tempfile, pt2trans_disttolerance)

# Adjust DL, DH, and Arm height to MHW
heightfields = ('DL_z','DH_z','DL_zMHW', 'DH_zMHW','Arm_z','Arm_zMHW')
for f in heightfields:
    if not fieldExists(extendedTransects,f):
        arcpy.AddField_management(extendedTransects,f,'DOUBLE')
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

"""
DistDH, DistDL, DistArm: Distance of dunes/armoring from MHW shoreline
"""
# Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
fieldlist = ["DistDH","DistDL","DistArm","SL_easting","SL_northing","DH_easting","DH_northing","DL_easting","DL_northing","Arm_easting","Arm_northing"]
for newfname in fieldlist:
    if not fieldExists(extendedTransects, newfname):
        arcpy.AddField_management(extendedTransects, newfname, "DOUBLE")
        print 'Added '+newfname+' field to '+extendedTransects
# ERROR below: 'operation was attempted on an empty geometry'
with arcpy.da.UpdateCursor(extendedTransects, fieldlist) as cursor:
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

"""
Dist2Inlet: Calc dist from inlets
# Requires transects and shoreline
"""
if not fieldExists(extendedTransects,'Dist2Inlet'):
     arcpy.AddField_management(extendedTransects, 'Dist2Inlet','DOUBLE')


# Convert shoreline to routes # Measure distance from inlet to each transect in both directions
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT') # Check that the inlet is southwest of the study area
arcpy.Intersect_analysis([extendedTransects,'shore_routeLL_temp'],'xptsroute_temp','ALL','1 METERS','POINT')
arcpy.LocateFeaturesAlongRoutes_lr('xptsroute_temp',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.DeleteField_management(extendedTransects, "MEAS") # in case of reprocessing
arcpy.JoinField_management(extendedTransects, transUIDfieldname, 'DistTableLL',transUIDfieldname, "MEAS")

arcpy.MakeFeatureLayer_management(shoreline,shoreline+'_lyr','"Join_Count">1') # Only use sections that intersect two inlet lines
arcpy.CreateRoutes_lr(shoreline+'_lyr',"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
# pull in intersect points
arcpy.LocateFeaturesAlongRoutes_lr('xptsroute_temp',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.JoinField_management(extendedTransects, transUIDfieldname, 'DistTableUR',transUIDfieldname, "MEAS")
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

DeleteTempFiles()
arcpy.Delete_management(os.path.join(home,"DistTableLL"))
arcpy.Delete_management(os.path.join(home,"DistTableUR"))


endPart1 = time.clock()
duration = endPart1 - startPart1
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 1 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''______________________________________________________________________________________________________________

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
Clip transects, get barrier widths, populate DH DL distances
Requires: extended transects, boundary polygon
'''

print "Starting Part 2"
startPart2 = time.clock()

# Clip transects with boundary polygon
arcpy.Clip_analysis(extendedTransects, barrierBoundary, baseName)

# Island width - total land (WidthLand), farthest sides (WidthFull), and segment (WidthPart)
ReplaceFields(baseName,{'WidthLand':'SHAPE@LENGTH'})

# Create simplified line for full barrier width that ignores interior bays: verts_temp > trans_temp > length_temp
arcpy.FeatureVerticesToPoints_management(baseName, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect
arcpy.PointsToLine_management("verts_temp","trans_temp",transUIDfieldname) # creates trans_temp: clipped transects with single vertices
arcpy.SimplifyLine_cartography("trans_temp", "length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP") # creates length_temp: removes extraneous bends while preserving essential shape; adds InLine_FID and SimLnFlag;
ReplaceFields("length_temp",{'WidthFull':'SHAPE@LENGTH'})
# Join clipped transects with full barrier lines and transfer width value
arcpy.JoinField_management(baseName, transUIDfieldname, "length_temp", transUIDfieldname, "WidthFull")

# Calc WidthPart as length of the part of the clipped transect that intersects MHW_oceanside
arcpy.MultipartToSinglepart_management(baseName,'singlepart_temp')
ReplaceFields("singlepart_temp",{'WidthPart':'SHAPE@LENGTH'})
"""
Adding WidthPart to T:\Commons_DeepDive\DeepDive\NewJersey\Forsythe\2014\Forsythe2014.gdb\singlepart_temp...
Failed to execute. Parameters are not valid.
ERROR 001334: Cannot delete required field Shape_Length
Failed to execute (DeleteField).
Failed to execute. Parameters are not valid.
ERROR 000368: Invalid input data.
Failed to execute (SelectLayerByLocation).

Runtime error Traceback (most recent call last): File "<string>", line 394, in <module> File "c:\arcgis\desktop10.3\arcpy\arcpy\management.py",
line 7359, in SelectLayerByLocation raise e ExecuteError: Failed to execute. Parameters are not valid. ERROR 000368: Invalid input data.
Failed to execute (SelectLayerByLocation).
"""
arcpy.SelectLayerByLocation_management('singlepart_temp', "INTERSECT", shoreline, '10 METERS')
arcpy.JoinField_management(baseName,transUIDfieldname,"singlepart_temp",transUIDfieldname,"WidthPart")

# Remove temp files
DeleteTempFiles()

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
print 'Should be quick!'
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
        # Find which of DL, DH, and Arm is closest to MLW and not Null (exclude DH if higher than maxDH)
        cp = FindNearestPointWithZvalue(row,cursor.fields,distfields,maxDH) # prefix of closest point metric
        if cp: # if closest point was found calculate beach width with that point, otherwise skip
            # Set values from each row
            d_x = row[cursor.fields.index(cp+'_easting')]
            d_y = row[cursor.fields.index(cp+'_northing')]
            b_slope = row[cursor.fields.index('Bslope')]
            sl_x = row[cursor.fields.index('SL_easting')]
            sl_y = row[cursor.fields.index('SL_northing')]
            d_z = row[cursor.fields.index(cp+'_zMHW')]

            # Calculate beach height
            beach_h_MLW = d_z-oMLW
            # Calculate beach width = Euclidean distance from dune (DL, DH, or Arm) to MLW
            mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_v2(oMLW,d_x,d_y,b_slope,sl_x,sl_y)

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
arcpy.MakeXYEventLayer_management(baseName,'MLW_easting','MLW_northing',MLWpts+'_lyr',utmSR)
arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)

arcpy.FeatureClassToFeatureClass_conversion(baseName,home,transects_final)

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

# Split transects into segments
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
"""
Replaced by Sort on transUIDfieldname and Dist_Seg below
# Create unique id SplitSort by sorting on transUIDfieldname and DistSeg
arcpy.AddField_management(transPts_presort,"id_temp","TEXT")
#Create temp file with points sorted by [transUIDfieldname]_[Dist_Seg] # Calc field - 24 seconds; cursor - 4.5 seconds
with arcpy.da.UpdateCursor(transPts_presort, (transUIDfieldname,'Dist_Seg','id_temp')) as cursor:
    for row in cursor:
        try:
            dist = str(int(row[1]))
        except:
            dist = 'Null' # Must be Null string instead of None
        row[2] = "%s_%s" % (str(row[0]), dist)
        cursor.updateRow(row)
"""
# Sort on transUIDfieldname and DistSeg (id_temp)
RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, tranSplitPts, [[transUIDfieldname,'ASCENDING'],['Dist_Seg','ASCENDING']])
ReplaceFields(tranSplitPts,{'SplitSort':'OID@'})

# Calculate DistSegDH = distance of point from dune crest
# Requires fields: DistDH, DistDL, DistArm, Dist_Seg
distfields = ['DistSegDH','DistSegDL','Dist_Seg','DistDH','DistDL','DistArm','DistSegArm']
for field in distfields:
    if not fieldExists(tranSplitPts,field):
        arcpy.AddField_management(tranSplitPts,field,'DOUBLE')
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

arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID"])

DeleteTempFiles()

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

# Extract elevation and slope at points
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
    arcpy.AddField_management(tranSplitPts,'PointZ_mhw',"DOUBLE")
    with arcpy.da.UpdateCursor(tranSplitPts,['PointZ','PointZ_mhw']) as cursor:
        for row in cursor:
            try:
                row[1] = row[0] - MHW
            except:
                pass
            cursor.updateRow(row)
    arcpy.CopyFeatures_management(tranSplitPts,pts_elevslope)

# Save pts as feature class with Nulls (transSplitPts_final)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts,home,tranSplitPts_null)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts,home,tranSplitPts_fill)
ReplaceValueInFC(tranSplitPts_fill,[], None, fill)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts_fill,out_dir,tranSplitPts_shp+'.shp')
arcpy.TableToTable_conversion(tranSplitPts_fill, out_dir, tranSplitPts_fill+'.csv')

finalmessage = "The final ("+tranSplitPts_shp+") were exported as a shapefile and CSV to "+out_dir+". \n" \
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
