'''
Deep dive Transect Extraction for Fire Island, NY 2012
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: sawyer.stippa@gmail.com; bgutierrez@usgs.gov; emilysturdivant@gmail.com
Date last modified: 1/25/2016

Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
'''

import arcpy, time, os
from math import radians, cos, asin, sin, atan2, sqrt, degrees
# Note: Run in ArcMap python window
# Turn off "auto display" in ArcMap preferences

# arcpy.GetParameterAsText(0)
############################################################################# Set environments
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\FireIsland_2012.gdb"
##################################### Inputs
# Interannually consistent:
site = 'FireIsland'
rawtransects = 'LongIsland_LT' 	# National Assessment transects-done
extendedTransects = 'FI_extTransects_2012' # Created MANUALLY: In an Edit session, duplicated a group of 30 extended NA transects and moved the new transects to fill the  gap
#jetty_line = 'FireIslandInlet'           # Manually digitized jetty line from Arc's Imagery Basemap with everything projected to NAD 83 UTM 18N
#finalinlet = 'NEInletTransect' # transect corresponding to NE inlet (opposite of canal)
MLW = -1.27 						# Beach height adjustment (relative to MHW)...adjusted smaller by 6 cm due to KW value of 0.46 for beach face and 0.52 from backbarrier tidal datum (Atl. Beach, NY)
fill = -99999	  					# Replace Nulls with
dMHW = -.46
extend = 2000 						# extended transects distance (m) IF NEEDED

# Year-specific
barrierBoundary = 'FI_Polygon_2012' 	# Barrier Boundary polygon
year = '2012'
dhPts = 'DHigh2012' 					# Dune crest,***NOTE: replace -99999 values will Null before running!!!
dlPts = 'DLow2012' 						# Dune toe,  ***NOTE: replace -99999 values will Null before running!!!
ShorelinePts = 'FireIslandMHWShore2012' 			# Shoreline points
MHW_oceanside = 'FireIsland_MHWline_2012v3'   # MHW, used to create BreezyBoundsPGon
inletLines = 'FI_inletLines_2012'
#elevGrid = 'bp11_dem_1m' 				# Elevation
#slopeGrid = 'BreezyPt_slope_'+year
#habitat = 'habitat_201211' 			# Habitat
############################################# Outputs
dh10 = 'DHigh_10m_'+year 							# DHigh within 10m
dl10 = 'DLow_10m_'+year						# DLow within 10m
SHL10 = 'SHLPts_10m_'+year							# beach slope from lidar within 10m of transect
shoreline = 'ShoreBetweenInlets_'+year        # Complete shoreline ready to become route in Pt. 2
baseName = 'trans_clip_working'         # Clipped transects			NOTE: 'StartX' and 'StartY' in code are UTM XYs stored here.
transects_final = site+'_'+year+'trans_clip'

#tranSin = 'transectSinglePart' 				# Single part transects
#tranSplit = 'trans_5m_Segments' 			# Transect Segments (5m)
#tranSplitPts = 'trans_5m_Segment_Points' 	# Outputs Transect Segment points
#transSplitPts_final = site+year+'_trans_5mSegPts'

start = time.clock()
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
Requires DH & DL points, NA transects
'''
print "Starting Part 1"
startPart1 = time.clock()

# Replace fill values with Null in dune heights:
with arcpy.da.UpdateCursor(dhPts, ("dhigh_z")) as cursor:
    for row in cursor:
        if row[0] == -99999:
            row[0] = None
            cursor.updateRow(row)
with arcpy.da.UpdateCursor(dlPts, ("dlow_z")) as cursor:
    for row in cursor:
        if row[0] == -99999:
            row[0] = None
            cursor.updateRow(row)

# Add ID field to DH and DL and populate with OBJECTID
arcpy.AddField_management(dhPts,'ID','SINGLE')
arcpy.AddField_management(dlPts,'ID','SINGLE')
arcpy.CalculateField_management(dhPts,"ID","!OBJECTID!","Python_9.3")
arcpy.CalculateField_management(dlPts,"ID","!OBJECTID!","Python_9.3")

# Extend transects if not already
if arcpy.Exists(extendedTransects) == 0:
    # Add extended length field and populate with legnth
    arcpy.AddField_management(rawtransects, 'LENGTH', 'LONG')
    arcpy.CalculateField_management(rawtransects, "LENGTH", extend, "Python_9.3")
    # Create extended transects
    arcpy.BearingDistanceToLine_management(rawtransects, extendedTransects, "StartX", "StartY", "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))
    # Join transect fields to extended transects
    arcpy.JoinField_management(extendedTransects, "TransOrder", rawtransects, "TransOrder", ["LRR","LR2","LSE","LCI90"])

##########
# MANUALLY added transects to the western edge: duplicated a group of 30 transects and moved the group to fill the transect gap
##########

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
transwork = extendedTransects + '_' + year
#arcpy.CopyFeatures_management(extendedTransects,transwork)
arcpy.Sort_management(extendedTransects,transwork,'TRANSORDER')
extendedTransects = transwork

# Join closest DH and DL within 10m to transects (create temp), join transects back, and save only those pts within 10m of transects
arcpy.SpatialJoin_analysis(extendedTransects,dhPts,'dh_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.SpatialJoin_analysis(extendedTransects,dlPts,'dl_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.AddJoin_management(dhPts,"ID",'dh_trans_temp',"ID","KEEP_COMMON")
arcpy.AddJoin_management(dlPts,"ID",'dl_trans_temp',"ID","KEEP_COMMON")
arcpy.CopyFeatures_management(dhPts, dh10)
arcpy.CopyFeatures_management(dlPts, dl10)
arcpy.RemoveJoin_management(dhPts)
arcpy.RemoveJoin_management(dlPts)

# Join DH fields to transects
arcpy.AddField_management(extendedTransects, 'DH_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_z', 'DOUBLE')

arcpy.JoinField_management(extendedTransects, "TransOrder", 'dh_trans_temp', "TransOrder", ["lon", "lat", "easting", "northing", "dhigh_z", ])

arcpy.CalculateField_management(extendedTransects, "DH_Lon", "!lon!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_Lat", "!lat!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_easting", "!easting!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_northing", "!northing!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_z", "!dhigh_z!", "Python_9.3")

arcpy.DeleteField_management(extendedTransects, "lon")
arcpy.DeleteField_management(extendedTransects, "lat")
arcpy.DeleteField_management(extendedTransects, "easting")
arcpy.DeleteField_management(extendedTransects, "northing")
arcpy.DeleteField_management(extendedTransects, "dhigh_z")

arcpy.Delete_management(os.path.join(home,"dh_trans_temp"))

# DL fields
arcpy.AddField_management(extendedTransects, 'DL_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_z', 'DOUBLE')

arcpy.JoinField_management(extendedTransects, "TransOrder", 'dl_trans_temp', "TransOrder", ["lon", "lat", "easting", "northing", "dlow_z", ])

arcpy.CalculateField_management(extendedTransects, "DL_Lon", "!lon!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_Lat", "!lat!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_easting", "!easting!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_northing", "!northing!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_z", "!dlow_z!", "Python_9.3")

arcpy.DeleteField_management(extendedTransects, "lon")
arcpy.DeleteField_management(extendedTransects, "lat")
arcpy.DeleteField_management(extendedTransects, "easting")
arcpy.DeleteField_management(extendedTransects, "northing")
arcpy.DeleteField_management(extendedTransects, "dlow_z")

arcpy.Delete_management(os.path.join(home,"dl_trans_temp"))

#Was in Pt 1 so that values would be preserved even if Clip segmented transects; actually, probably doesn't matter because clip creates multipart features
arcpy.AddField_management(ShorelinePts,'ID','SINGLE')
arcpy.CalculateField_management(ShorelinePts,"ID","!OBJECTID!","Python_9.3")

arcpy.SpatialJoin_analysis(extendedTransects,ShorelinePts,'SHL_trans_temp','#','#','#',"CLOSEST","10 meters") # 10 meters here, but in SSorig, this isn't included
arcpy.AddJoin_management(ShorelinePts,"ID",'SHL_trans_temp',"ID","KEEP_COMMON")
arcpy.CopyFeatures_management(ShorelinePts, SHL10)
arcpy.RemoveJoin_management(ShorelinePts)

# ShorelinePts fields
arcpy.AddField_management(extendedTransects, 'ShL_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'ShL_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'ShL_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'ShL_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'Bslope', 'DOUBLE')

arcpy.JoinField_management(extendedTransects, "TransOrder", 'SHL_trans_temp', "TransOrder", ["lon", "lat", "easting", "northing", "slope"]) # SSorig joined sl_x and slope, not easting&northing

arcpy.CalculateField_management(extendedTransects, "ShL_Lon", "!lon!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "ShL_Lat", "!lat!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "ShL_easting", "!easting!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "ShL_northing", "!northing!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "Bslope", "!slope!", "Python_9.3")

arcpy.DeleteField_management(extendedTransects, "lon")
arcpy.DeleteField_management(extendedTransects, "lat")
arcpy.DeleteField_management(extendedTransects, "easting")
arcpy.DeleteField_management(extendedTransects, "northing")
arcpy.DeleteField_management(extendedTransects, "slope")

arcpy.Delete_management(os.path.join(home,"SHL_trans_temp"))

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

# Clip transects with boundary polygon
arcpy.Clip_analysis(extendedTransects, barrierBoundary, baseName)

# Create simplified line for full barrier width
arcpy.FeatureVerticesToPoints_management(baseName, baseName + "_verts_temp", "BOTH_ENDS") # creates _verts_temp
arcpy.PointsToLine_management(baseName + "_verts_temp",baseName + "_trans_temp","TransOrder") # creates _trans_temp from _verts_temp
arcpy.SimplifyLine_cartography(baseName + "_trans_temp", baseName + "_length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP") # creates _length_temp from _trans_temp

# Add and populate fields
arcpy.AddField_management(baseName, "WidthFull", "DOUBLE")
arcpy.AddField_management(baseName, "WidthLand", "DOUBLE")
arcpy.AddField_management(baseName + "_length_temp", "Width", "DOUBLE")
arcpy.CalculateField_management(baseName,"WidthLand","!SHAPE_Length!","PYTHON")
arcpy.CalculateField_management(baseName + "_length_temp","Width","!SHAPE_Length!","PYTHON")

# Join clipped transects with full barrier lines and transfer width value
arcpy.JoinField_management(baseName, "TransOrder", baseName + "_length_temp","TransOrder", "Width") # EJS: joins _length_temp to baseName
arcpy.CalculateField_management(baseName,"WidthFull", "!Width!","PYTHON")

# Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
arcpy.AddField_management(baseName, "DistDH", "DOUBLE")
arcpy.AddField_management(baseName, "DistDL", "DOUBLE")
arcpy.CalculateField_management(baseName, "DistDH",'math.sqrt((!ShL_easting! - !DH_easting!) * (!ShL_easting! - !DH_easting!) + (!DH_northing! - !ShL_northing!) * (!DH_northing! - !ShL_northing!))',"PYTHON", '#')
arcpy.CalculateField_management(baseName, "DistDL",'math.sqrt((!ShL_easting! - !DL_easting!) * (!ShL_easting! - !DL_easting!) + (!DL_northing! - !ShL_northing!) * (!DL_northing! - !ShL_northing!))',"PYTHON", '#')

# Remove temp files
arcpy.Delete_management(os.path.join(home,baseName + "_length_temp"))
arcpy.Delete_management(os.path.join(home,baseName + "_trans_temp"))
arcpy.Delete_management(os.path.join(home,baseName + "_verts_temp"))

# Calc dist from inlets
# Major update to produce distance to closest inlet
# Changed fieldname - check if needs to be changed back.
"""
Inlet lines: manually create lines based on the boundary polygon that correspond to end of land and cross the MHW line
"""
# Create shoreline if it does not already exist
if arcpy.Exists(shoreline) == 0:
    # Create oceanside line that begins at jetty (canalPt) = 'shoreline'
    arcpy.Intersect_analysis([inletLines,MHW_oceanside],'trans_canalpts_temp','ONLY_FID','1 METERS','POINT') # temp1_pts
    arcpy.SplitLineAtPoint_management(MHW_oceanside,'trans_canalpts_temp','Ocean_split_temp','1 Meters')
    arcpy.MultipartToSinglepart_management("Ocean_split_temp", "Ocean_split_temp_singlepart")
    arcpy.Select_analysis('Ocean_split_temp_singlepart',shoreline,'Shape_Length >0.01')
    # Merge and then extend shoreline to inlet lines
    #arcpy.Merge_management(['shoreline_temp',jetty_line,finalinlet],shoreline)
    #arcpy.ExtendLine_edit(shoreline,'250 Meters')
    #arcpy.TrimLine_edit(shoreline, dangle_length="3100 Meters", delete_shorts="DELETE_SHORT") ### NEW = check
    # Remove temp files
    arcpy.Delete_management(os.path.join(home,'trans_canalline_temp'))
    arcpy.Delete_management(os.path.join(home,'trans_canalpts_temp'))
    arcpy.Delete_management(os.path.join(home,'Ocean_split_temp'))
    arcpy.Delete_management(os.path.join(home,'Ocean_split_temp_singlepart'))
else:
    pass

# Convert shoreline to routes, find intersection with transects, create distance tables, and join distance to baseName and take shortest distance
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

# Remove temp files
arcpy.Delete_management(os.path.join(home,"shore_routeUR_temp"))
arcpy.Delete_management(os.path.join(home,"shore_routeLL_temp"))
arcpy.Delete_management(os.path.join(home,"DistTableUR"))
arcpy.Delete_management(os.path.join(home,"DistTableLL"))
arcpy.Delete_management(os.path.join(home,"xpts"))

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

# EJS: Calc DL and DH height above MHW
arcpy.AddField_management(baseName, 'DL_zMHW', 'DOUBLE')
arcpy.AddField_management(baseName, 'DH_zMHW', 'DOUBLE')
arcpy.CalculateField_management(baseName, 'DL_zMHW','!DL_z!' + str(dMHW),"PYTHON",'#')
arcpy.CalculateField_management(baseName, 'DH_zMHW','!DH_z!' + str(dMHW),"PYTHON",'#')

# Prepare to calculate additional beach parameters
arcpy.AddField_management(baseName, 'beach_h_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'delta_xm_MLW', 'DOUBLE')

# Calculate MHW and MLW position and beach width
cursor = arcpy.UpdateCursor(baseName)
for row in cursor:
    skip = 0
    # 1 Calculate Beach height from MHW and MLW
    # if dune toe is missing or bogus, use dhigh instead
    if row.getValue('DL_zMHW') is not None:
        lon1 = radians(row.getValue('DL_Lon'))
        lat1 = radians(row.getValue('DL_Lat'))
        row.setValue('beach_h_MLW', row.getValue('DL_zMHW')- MLW) ###
    elif (row.getValue('DL_zMHW') is None) and (row.getValue('DH_zMHW') is not None) and (row.getValue('DH_zMHW') < 2.5):
        lon1 = radians(row.getValue('DH_Lon'))
        lat1 = radians(row.getValue('DH_Lat'))
        row.setValue('beach_h_MLW', row.getValue('DH_zMHW') - (MLW))
    else:
        skip = 1
    if skip == 0:
        r = 6371 # Radius of earth in meters
        if row.getValue('Bslope') is not None:
            # 2 Calculate Euclidean distance between dune and MHW Shoreline
            row.setValue('delta_xm_MLW', abs(row.getValue('beach_h_MLW')/row.getValue('Bslope')))    # modified with 'Bslope' on 12/3/2015 #code hang-up
    cursor.updateRow(row)

endPart4 = time.clock()
duration = endPart4 - startPart4
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 4 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

arcpy.CopyFeatures_management(baseName,transects_final)

# Replace null values with -99999 for final transects file, before segmenting
fields = arcpy.ListFields(transects_final) # list of fields in points
cursor = arcpy.UpdateCursor(transects_final)
for row in cursor:
   for field in fields:
       if row.getValue(field.name) is None:
           row.setValue(field.name,fill)
           cursor.updateRow(row)
       else:
           pass


print "Creation of " + transects_final + " completed. "
#print "Creation of " + transects_final + " completed. Proceeding to create 5m segments and points."


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
Requires: clipped transects, DH10m DL10m, elevation, slope, recharge, Habitat
'''

print 'Starting Part 5'
startPart5 = time.clock()

# Convert Multipart transects to indivicual parts
arcpy.MultipartToSinglepart_management(baseName, tranSin)

# Split transects into segments
#arcpy.XToolsGP_SplitPolylines_xtp(tranSin,home+ '\\' + tranSplit,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
#input = os.path.join(home,tranSin) # os.path.join produces the wrong backslash: '\\' instead of r'/'
#output = os.path.join(home,tranSplit)
input = home + '/' + tranSin
output = home + '/' + tranSplit
arcpy.XToolsGP_SplitPolylines_xtp(input,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
#arcpy.FeatureClassToFeatureClass_conversion(output, home,tranSplit) #Save in actual working workspace

# Segments to center points
arcpy.FeatureToPoint_management(tranSplit,tranSplitPts)

# Add xy for each segment center point
arcpy.AddField_management(tranSplitPts,"seg_x", "DOUBLE")
arcpy.AddField_management(tranSplitPts,"seg_y", "DOUBLE")
arcpy.CalculateField_management(tranSplitPts,"seg_x","!shape.firstpoint.X!","PYTHON_9.3")
arcpy.CalculateField_management(tranSplitPts,"seg_y","!shape.firstpoint.Y!","PYTHON_9.3")

# Get transect start xy and calc dist_seg (dist from MHW oceanside)
#arcpy.JoinField_management(tranSplitPts,"TransOrder",tranStartPts,"TransOrder",["StartX","StartY"])
arcpy.AddField_management(tranSplitPts,"Dist_Seg","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'Dist_Seg', 'math.sqrt((( !seg_x! - !ShL_easting! ) * ( !seg_x! - !ShL_easting!)) + (( !seg_y! - !ShL_northing! ) * ( !seg_y! - !ShL_northing!)))', "PYTHON", '#')

#Calc unique id SplitSort by sorting on TransOrder and DistSeg
arcpy.AddField_management(tranSplitPts,"id_temp","TEXT")
arcpy.AddField_management(tranSplitPts,"dist_temp","LONG")
arcpy.CalculateField_management(tranSplitPts,"dist_temp","!Dist_Seg!","PYTHON")
arcpy.CalculateField_management(tranSplitPts, 'id_temp', '"%s_%s" % ( !TransOrder!, !dist_temp!)', 'PYTHON', '#')
arcpy.Sort_management(tranSplitPts, tranSplitPts + "_sort_temp", 'TransOrder ASCENDING;Dist_Seg ASCENDING')
arcpy.AddField_management(tranSplitPts + "_sort_temp","SplitSort","LONG")
arcpy.CalculateField_management(tranSplitPts + "_sort_temp", 'SplitSort', '!OBJECTID!', 'PYTHON', '#')
arcpy.JoinField_management(tranSplitPts,"id_temp",tranSplitPts + "_sort_temp","id_temp","SplitSort") ##################### may take a while

# UPDATED: Get dist to dune (only for transects with a matlab DH/DL output within 10m) - replaced what is commented out below
arcpy.AddField_management(tranSplitPts,"DistSegDH","DOUBLE")
arcpy.AddField_management(tranSplitPts,"DistSegDL","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'DistSegDH', "!DistDH!-!Dist_Seg!",'PYTHON')
arcpy.CalculateField_management(tranSplitPts, 'DistSegDL', "!DistDL!-!Dist_Seg!",'PYTHON')

"""
# Replaced with above 'Get dist to dune'
#Get dist to dune high (only for transects with a matlab DH/DL output within 10m)
#arcpy.JoinField_management(tranSplitPts,"TransOrder",dh10,"dh_trans_temp_TransOrder",["DHigh_easting","DHigh_northing"]) ##################### may take a while
arcpy.JoinField_management(tranSplitPts,"TransOrder",dh10,"dh_trans_temp_TransOrder",["dh_trans_temp_east_sm","dh_trans_temp_north_sm"]) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"DistSegDH","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'DistSegDH', 'math.sqrt((( !seg_x! - !dh_trans_temp_east_sm! ) * ( !seg_x! - !dh_trans_temp_east_sm!)) + (( !seg_y! - !dh_trans_temp_north_sm! ) * ( !seg_y! - !dh_trans_temp_north_sm!)))', "PYTHON", '#')
arcpy.DeleteField_management(tranSplitPts,["dh_trans_temp_east_sm","dh_trans_temp_north_sm"])

#Get dist to dune low
arcpy.JoinField_management(tranSplitPts,"TransOrder",dl10,"dl_trans_temp_TransOrder",["dl_trans_temp_east_sm","dl_trans_temp_north_sm"]) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"DistSegDL","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'DistSegDL', 'math.sqrt((( !seg_x! - !dl_trans_temp_east_sm! ) * ( !seg_x! - !dl_trans_temp_east_sm!)) + (( !seg_y! - !dl_trans_temp_north_sm! ) * ( !seg_y! - !dl_trans_temp_north_sm!)))', "PYTHON", '#')
arcpy.DeleteField_management(tranSplitPts,["dl_trans_temp_east_sm","dl_trans_temp_north_sm"])
"""

# Create slope grid if doesn't already exist
if arcpy.Exists(slopeGrid) == 0:
    arcpy.Slope_3d(elevGrid,slopeGrid,'PERCENT_RISE')

#Get elevation and slope at points
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,elevGrid)
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,slopeGrid)
arcpy.AddField_management(tranSplitPts,"PointZ","DOUBLE")
arcpy.AddField_management(tranSplitPts,"PointSlp","DOUBLE")
elev = '!%s!' %elevGrid
slope = '!%s!' %slopeGrid
arcpy.CalculateField_management(tranSplitPts, "PointZ",elev,"PYTHON")
arcpy.CalculateField_management(tranSplitPts,"PointSlp",slope,"PYTHON")

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
arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID","id_temp","dist_temp",elevGrid,slopeGrid])
arcpy.Delete_management(home+'/'+ tranSplitPts + "_sort_temp")

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
Requires:  Segment Points
'''
arcpy.AddMessage("Starting Part 6")
startPart6 = time.clock()

arcpy.CopyFeatures_management(tranSplitPts,transSplitPts_final)

# Replace Nulls with fill for export to shapefile and manipulation in Matlab
fields = arcpy.ListFields(transSplitPts_final) # list of fields in points
cursor = arcpy.UpdateCursor(transSplitPts_final)
for row in cursor:
    for field in fields:
        if row.getValue(field.name) is None:
            row.setValue(field.name,fill)
            cursor.updateRow(row)
        else:
            pass

endPart6 = time.clock()
duration = endPart6 - startPart6
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 6 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

end = time.clock()
duration = end - start
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Processing completed in %dh:%dm:%fs" % (hours, minutes, seconds)
