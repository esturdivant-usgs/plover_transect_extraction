'''
Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Sawyer Stippa
email: sawyer.stippa@gmail.com
Date last modified: 10/21/2015
'''

import arcpy, time
from math import radians, cos, asin, sin, atan2, sqrt, degrees
# Note: Run in ArcMap python window
# Turn off "auto display" in ArcMap preferences

#arcpy.GetParameterAsText(0)
############################################################################# Set environments
arcpy.env.overwriteOutput = True 						# Overwrite output?
arcpy.CheckOutExtension("Spatial") 						# Checkout Spatial Analysis extentsion
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 			# Add XTools Pro toolbox
arcpy.env.workspace=home= r'C:/Users/SSTIPPA/Desktop/ASIS/ASIS_2012.gdb' 	# Get workspace
##################################### Inputs 
transects = 'DelmarvaN_LT' 			# National Assessment transects
dhPts = 'DHigh' 					# Dune crest
dlPts = 'DLow' 						# Dune toe
barrierBoundary = 'ASIS_BND_2013' 	# Barrier Boundary
shorelinePts = 'SL_LRR' 			# Shoreline points
recharge = "recharge_2008" 			# Recharge
elevGrid = 'elev_2012' 				# Elevation
slopeGrid = 'slope_2012' 			# Slope
habitat = 'habitat_201211' 			# Habitat
extend = 6000 						# extended transects distance (m)
MLW = -0.66 						# Beach height adjustment (from MHW)
fill = 9999.9999  					# Replace Nulls with 
############################################# Outputs
dh10 = 'DHigh_10m' 							# DHigh within 10m
dl10 = 'DLow_10m' 							# DLow within 10m
extendedTransects = 'transects_extended' 	# Extended transects
baseName = 'trans_clip2BND' 				# Clipped transecst
tranSin = 'transectSinglePart' 				# Single part transects
tranSplit = 'trans_5m_Segments' 			# Transect Segments (5m)
tranSplitPts = 'trans_5m_Segment_Points' 	# Outputs Transect Segment points

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

# Add extended length field and populate with legnth 
arcpy.AddField_management(transects, 'LENGTH', 'LONG') # ERROR: table is not editable
arcpy.CalculateField_management(transects, "LENGTH", extend, "Python_9.3")

# Create extended transects
arcpy.BearingDistanceToLine_management(transects, extendedTransects, "StartX", "StartY", "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))

# Join transect fields to extended transects
arcpy.JoinField_management(extendedTransects, "TransOrder", transects, "TransOrder", ["LRR","LR2","LSE","LCI90"])

# Add ID field to DH and DL and populate with OBJECTID - unique ID field needed for spatial join
arcpy.AddField_management(dhPts,'ID','SINGLE')
arcpy.AddField_management(dlPts,'ID','SINGLE')
arcpy.CalculateField_management(dhPts,"ID","!OBJECTID!","Python_9.3")
arcpy.CalculateField_management(dlPts,"ID","!OBJECTID!","Python_9.3")

# Join closest DH and DL within 10m to transects (create temp)
arcpy.SpatialJoin_analysis(extendedTransects,dhPts,'dh_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.SpatialJoin_analysis(extendedTransects,dlPts,'dl_trans_temp','#','#','#',"CLOSEST","10 meters")

# Join transects back to DH and DL
arcpy.AddJoin_management(dhPts,"ID",'dh_trans_temp',"ID","KEEP_COMMON")
arcpy.AddJoin_management(dlPts,"ID",'dl_trans_temp',"ID","KEEP_COMMON")

# Save only the DH and DL that are within 10m as new layers
arcpy.CopyFeatures_management(dhPts, dh10)
arcpy.CopyFeatures_management(dlPts, dl10)

# Remove Join
arcpy.RemoveJoin_management(dhPts)
arcpy.RemoveJoin_management(dlPts)

# Join DH and DL fields to transects
arcpy.AddField_management(extendedTransects, 'DH_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_z', 'DOUBLE')

arcpy.AddField_management(extendedTransects, 'DL_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_z', 'DOUBLE')

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
arcpy.DeleteField_management(extendedTransects, "Azimuth")
arcpy.DeleteField_management(extendedTransects, "LENGTH")

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

# Delete temp 
arcpy.Delete_management("dh_trans_temp")
arcpy.Delete_management("dl_trans_temp")

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
arcpy.FeatureVerticesToPoints_management(baseName, baseName + "_verts_temp", "BOTH_ENDS")
arcpy.PointsToLine_management(baseName + "_verts_temp",baseName + "_trans_temp","TransOrder")
arcpy.SimplifyLine_cartography(baseName + "_trans_temp", baseName + "_length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP")

# Add and populate fields
arcpy.AddField_management(baseName, "WidthFull", "DOUBLE")
arcpy.AddField_management(baseName, "WidthLand", "DOUBLE")
arcpy.AddField_management(baseName + "_length_temp", "Width", "DOUBLE")
arcpy.CalculateField_management(baseName,"WidthLand","!Shape_Length!","PYTHON")
arcpy.CalculateField_management(baseName + "_length_temp","Width","!Shape_Length!","PYTHON")

# Join clipped transects with full barrier lines and transfer width value
arcpy.JoinField_management(baseName, "TransOrder", baseName + "_length_temp","TransOrder", "Width")
arcpy.CalculateField_management(baseName,"WidthFull", "!Width!","PYTHON")

# Add start lat and lon (nad83, decimal degrees)
#arcpy.JoinField_management(baseName, "TransOrder", startPts,"TransOrder", ["Start_lat","Start_lon"])

# Calc DistDH and DistDL
arcpy.AddField_management(baseName, "DistDH", "DOUBLE")
arcpy.AddField_management(baseName, "DistDL", "DOUBLE")
arcpy.CalculateField_management(baseName, "DistDH", 'math.sqrt((!StartX! - !DH_easting!) * (!StartX! - !DH_easting!) + (!DH_northing! - !StartY!) * (!DH_northing! - !StartY!))', "PYTHON", '#')
arcpy.CalculateField_management(baseName, "DistDL", 'math.sqrt((!StartX! - !DL_easting!) * (!StartX! - !DL_easting!) + (!DL_northing! - !StartY!) * (!DL_northing! - !StartY!))', "PYTHON", '#')

# Remove temp files
arcpy.Delete_management(baseName + "_length_temp")
arcpy.Delete_management(baseName + "_trans_temp")
arcpy.Delete_management(baseName + "_verts_temp")
#arcpy.Delete_management("StartPtsTemp")


'''# Calc dist from canal
arcpy.CreateRoutes_lr("MHW_2008_oceanside","ID","MHW_2008_oceanside_route_temp","LENGTH")
arcpy.LocateFeaturesAlongRoutes_lr(startPts, "MHW_2008_oceanside_route_temp", 'ID', '0 Meters', "tableDistCanal_temp", 'RID POINT MEAS', 'FIRST', 'DISTANCE', 'ZERO', 'FIELDS', 'M_DIRECTON')
arcpy.JoinField_management(baseName, "TransOrder", "tableDistCanal_temp","TransOrder", "MEAS")
arcpy.CalculateField_management(baseName, "DistToCana", "!MEAS!", "PYTHON")
arcpy.DeleteField_management(baseName, "MEAS")

arcpy.Delete_management("MHW_2008_oceanside_route_temp")
arcpy.Delete_management("tableDistCanal_temp")
'''

endPart2 = time.clock()
duration = endPart2 - startPart2
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\               /\\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////              /\\\///////\\\
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                  \///      /\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                         /\\\//
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                        \////\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                          \//\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                  /\\\      /\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                 \///\\\\\\\\\/
          \///              \///        \///  \///        \///        \///                   \/////////
______________________________________________________________________________________________________________
Get recharge percentage
Assign [class] values to new integer field [code] (beach=1, shrubforest=2, wetlands=3, unknown=4)
Requires clipped transects and recharge
'''
print "Starting Part 3"
startPart3 = time.clock()

# Select recharge polygons that are intersected by transects and copy to new recharge subset
arcpy.MakeFeatureLayer_management(recharge,'rechLayer')
arcpy.SelectLayerByLocation_management('rechLayer',"INTERSECT",baseName)
arcpy.management.CopyFeatures('rechLayer',"temprecharge")

# Convert recharge poly subset to raster
arcpy.FeatureToRaster_conversion("temprecharge","class","tempRechRas",1)

# Tabulate number of 1m cells off each class/code intersected by transect
arcpy.sa.TabulateArea(baseName,"TransOrder","tempRechRas","Value","tempTableByCode",1)

# Add percent fields to tabulated codes table
arcpy.management.AddField("tempTableByCode","perc1","DOUBLE")
arcpy.management.AddField("tempTableByCode","perc2","DOUBLE")
arcpy.management.AddField("tempTableByCode","perc3","DOUBLE")
arcpy.management.AddField("tempTableByCode","perc4","DOUBLE")

# Calc percent fields 
arcpy.CalculateField_management('tempTableByCode', 'perc1', '100* (!VALUE_1!/( !VALUE_1! + !VALUE_2! + !VALUE_3! + !VALUE_4!))', 'Python_9.3', '#')
arcpy.CalculateField_management('tempTableByCode', 'perc2', '100* (!VALUE_2!/( !VALUE_1! + !VALUE_2! + !VALUE_3! + !VALUE_4!))', 'Python_9.3', '#')
arcpy.CalculateField_management('tempTableByCode', 'perc3', '100* (!VALUE_3!/( !VALUE_1! + !VALUE_2! + !VALUE_3! + !VALUE_4!))', 'Python_9.3', '#')
arcpy.CalculateField_management('tempTableByCode', 'perc4', '100* (!VALUE_4!/( !VALUE_1! + !VALUE_2! + !VALUE_3! + !VALUE_4!))', 'Python_9.3', '#')

# Join back to transects and calc veg %
arcpy.JoinField_management(baseName,"TransOrder","tempTableByCode","TRANSORDER",["perc1","perc2","perc3","perc4"])
arcpy.AddField_management(baseName,"percBeach","DOUBLE")
arcpy.AddField_management(baseName,"percSF","DOUBLE")
arcpy.AddField_management(baseName,"percWet","DOUBLE")
arcpy.AddField_management(baseName,"percUnk","DOUBLE")
arcpy.CalculateField_management(baseName,"percBeach","!perc1!","PYTHON")
arcpy.CalculateField_management(baseName,"percSF","!perc2!","PYTHON")
arcpy.CalculateField_management(baseName,"percWet","!perc3!","PYTHON")
arcpy.CalculateField_management(baseName,"percUnk","!perc4!","PYTHON")
arcpy.DeleteField_management(baseName,["perc1","perc2","perc3","perc4"])

#Delete layers
arcpy.Delete_management("temprecharge")
arcpy.Delete_management("tempRechRas")
arcpy.Delete_management("tempTableByCode")

endPart3 = time.clock()
duration = endPart3 - startPart3
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 3 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

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

# Add Lon Lat Fields to shorelinePts
arcpy.AddXY_management(shorelinePts)
arcpy.AddField_management(shorelinePts, 'SL_Lon', 'DOUBLE')
arcpy.AddField_management(shorelinePts, 'SL_Lat', 'DOUBLE')
arcpy.CalculateField_management(shorelinePts, 'SL_Lon', '!POINT_X!', 'Python_9.3', '#')
arcpy.CalculateField_management(shorelinePts, 'SL_Lat', '!POINT_Y!', 'Python_9.3', '#')
arcpy.DeleteField_management(shorelinePts,['POINT_X','POINT_Y'])

# Join Transects with closest shorelinePts
arcpy.SpatialJoin_analysis(baseName,shorelinePts,'trans_temp', '#', '#', '#', "CLOSEST")
arcpy.JoinField_management(baseName, "TransOrder", 'trans_temp', "TransOrder", ["sl_x", "slope", "SL_Lon", "SL_Lat"])

# add fields
arcpy.AddField_management(baseName, 'beach_h_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'delta_xm_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'delta_x_gc_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'azimuth_SL', 'DOUBLE')
arcpy.AddField_management(baseName, 'MLW_Lon', 'DOUBLE')
arcpy.AddField_management(baseName, 'MLW_Lat', 'DOUBLE')
arcpy.AddField_management(baseName, 'beachWidth_MLW', 'DOUBLE')

# Calculate MHW and MLW position and beach width
cursor = arcpy.UpdateCursor(baseName)
for row in cursor:
    skip = 0
    # 1 Calculate Beach height from MHW and MLW
    # if dune toe is missing or bogus, use dhigh instead
    if row.getValue('DL_z') is not None:
        lon1 = radians(row.getValue('DL_Lon'))
        lat1 = radians(row.getValue('DL_Lat'))

        row.setValue('beach_h_MLW', row.getValue('DL_z') - (MLW))
    elif (row.getValue('DL_z') is None) and (row.getValue('DH_z') is not None) and (row.getValue('DH_z') < 3):
        lon1 = radians(row.getValue('DH_Lon'))
        lat1 = radians(row.getValue('DH_Lat'))

        row.setValue('beach_h_MLW', row.getValue('DH_z') - (MLW))
    else:
        skip = 1

    if skip == 0:

        # 2 Calculate Euclidean distance between dune and MHW Shoreline
        row.setValue('delta_xm_MLW', abs(row.getValue('beach_h_MLW')/sin(row.getValue('slope'))))

        # 3 Convert chord distance to Angular distance along great circle (gc)
        r = 6371 # Radius of earth in meters
        mlwKM = row.getValue('delta_xm_MLW')/1000
        d2 = 2 * asin(mlwKM/(2*r))
        row.setValue('delta_x_gc_MLW', d2)

        # 4 Find Azimuth between dune and MHW shoreline
        lon2 = radians(row.getValue('SL_Lon'))
        lat2 = radians(row.getValue('SL_Lat'))
        dlon = radians(row.getValue('SL_Lon') - degrees(lon1))
        dlat = radians(row.getValue('SL_Lat') - degrees(lat1))
        x = sin(dlon) * cos(lat2)
        y = (cos(lat1) * sin(lat2)) - (sin(lat1) * cos(lat2) * cos(dlon))
        theta = atan2(x,y)
        if degrees(theta) < 0:
            phi = degrees(theta)+360
        else:
            phi = degrees(theta)
        row.setValue('azimuth_SL', phi)
        phiR = radians(phi)

        # 5 Calculate Position of MLW shoreline
        latMLW = asin((sin(lat2) * cos(d2)) + (cos(lat2) * sin(d2) * cos(phiR)))
        lonMLW = lon2 + atan2(sin(phiR)*sin(d2)*cos(lat2), cos(d2)-sin(lat2)*sin(latMLW))
        row.setValue('MLW_Lat', degrees(latMLW))
        row.setValue('MLW_Lon', degrees(lonMLW))

        # 6 Calculate beach width from dune to MLW shoreline
        lon2 = radians(row.getValue('MLW_Lon'))
        lat2 = radians(row.getValue('MLW_Lat'))
        dlon = radians(row.getValue('MLW_Lon') - degrees(lon1))
        dlat = radians(row.getValue('MLW_Lat') - degrees(lat1))
        a = (sin(dlat/2) * sin(dlat/2)) + (cos(lat1) * cos(lat2) * (sin(dlon/2) * sin(dlon/2)))
        c = 2 * atan2(sqrt(a), sqrt(1-a)) # Angular distance in radians
        dMLW = r * c  # Distance (m) between dune and MLW
        row.setValue('beachWidth_MLW', dMLW*1000)
    else:
        pass

    cursor.updateRow(row)

# Delete Temp
arcpy.Delete_management('trans_temp')

endPart4 = time.clock()
duration = endPart4 - startPart4
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 4 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________________________________________________________________________________________________

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\             /\\\\\\\\\\\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////             \/\\\///////////
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                  \/\\\
     \/\\\\\\\\\\\\\/  \/\\\       \/\\\ \/\\\\\\\\\\\/          \/\\\                  \/\\\\\\\\\\\\
      \/\\\/////////    \/\\\\\\\\\\\\\\\ \/\\\//////\\\          \/\\\                   \////////////\\\
       \/\\\             \/\\\/////////\\\ \/\\\    \//\\\         \/\\\                             \//\\\
        \/\\\             \/\\\       \/\\\ \/\\\     \//\\\        \/\\\                  /\\\        \/\\\
         \/\\\             \/\\\       \/\\\ \/\\\      \//\\\       \/\\\                 \//\\\\\\\\\\\\\/
          \///              \///        \///  \///        \///        \///                   \/////////////
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
input = home + '/' + tranSin
output = home + '/' + tranSplit
arcpy.XToolsGP_SplitPolylines_xtp(input,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
arcpy.FeatureClassToFeatureClass_conversion(output, home,tranSplit) #Save in actual working workspace

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
arcpy.CalculateField_management(tranSplitPts, 'Dist_Seg', 'math.sqrt((( !seg_x! - !StartX! ) * ( !seg_x! - !StartX!)) + (( !seg_y! - !StartY! ) * ( !seg_y! - !StartY!)))', "PYTHON", '#')

#Calc unique id SplitSort by sorting on TransOrder and DistSeg
arcpy.AddField_management(tranSplitPts,"id_temp","TEXT")
arcpy.AddField_management(tranSplitPts,"dist_temp","LONG")
arcpy.CalculateField_management(tranSplitPts,"dist_temp","!Dist_Seg!","PYTHON")
arcpy.CalculateField_management(tranSplitPts, 'id_temp', '"%s_%s" % ( !TransOrder!, !dist_temp!)', 'PYTHON', '#')
arcpy.Sort_management(tranSplitPts, tranSplitPts + "_sort_temp", 'TransOrder ASCENDING;Dist_Seg ASCENDING')
arcpy.AddField_management(tranSplitPts + "_sort_temp","SplitSort","LONG")
arcpy.CalculateField_management(tranSplitPts + "_sort_temp", 'SplitSort', '!OBJECTID!', 'PYTHON', '#')
arcpy.JoinField_management(tranSplitPts,"id_temp",tranSplitPts + "_sort_temp","id_temp","SplitSort") ##################### may take a while

#Get dist to dune high (only for transects with a matlab DH/DL output within 10m)
arcpy.JoinField_management(tranSplitPts,"TransOrder",dh10,"dh_trans_temp_TransOrder",["DHigh_easting","DHigh_northing"]) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"DistSegDH","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'DistSegDH', 'math.sqrt((( !seg_x! - !DHigh_easting! ) * ( !seg_x! - !DHigh_easting!)) + (( !seg_y! - !DHigh_northing! ) * ( !seg_y! - !DHigh_northing!)))', "PYTHON", '#')
arcpy.DeleteField_management(tranSplitPts,["DHigh_easting","DHigh_northing"])

#Get dist to dune low
arcpy.JoinField_management(tranSplitPts,"TransOrder",dl10,"dl_trans_temp_TransOrder",["DLow_easting","DLow_northing"]) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"DistSegDL","DOUBLE")
arcpy.CalculateField_management(tranSplitPts, 'DistSegDL', 'math.sqrt((( !seg_x! - !DLow_easting! ) * ( !seg_x! - !DLow_easting!)) + (( !seg_y! - !DLow_northing! ) * ( !seg_y! - !DLow_northing!)))', "PYTHON", '#')

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

#Recharge
rechFields = ['zone','Rech','class']
arcpy.SpatialJoin_analysis(tranSplitPts,recharge,"rechargeJoin","JOIN_ONE_TO_ONE","KEEP_ALL") ##################### may take a while

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
arcpy.SpatialJoin_analysis(tranSplitPts,habitat,"habitatJoin","JOIN_ONE_TO_ONE","KEEP_ALL") ##################### may take a while

#assign new field name HabNPS and copy from join table	
arcpy.JoinField_management(tranSplitPts,'SplitSort',"habitatJoin",'SplitSort',habFields) ##################### may take a while
arcpy.AddField_management(tranSplitPts,"HabNPS","TEXT")
arcpy.CalculateField_management(tranSplitPts, 'HabNPS', '!Veg_Type!',"PYTHON")
arcpy.DeleteField_management(tranSplitPts,'Veg_Type')
arcpy.Delete_management("habitatJoin")

#Transect average Recharge
#arcpy.Intersect_analysis('Transects_North_MorphVariables_050812 #;Recharge_modNov18_subset #', r'F:\ASIS\TransectPopulation_v2\Tools\Testing_gdb.gdb\trans_rech_temp', 'ALL', '#', 'INPUT')
#arcpy.DeleteField_management('trans_rech_temp', 'FID_Transects_North_MorphVariables_050812;WidthFull;WidthLand;percBeach;percSF;percWet;percUnk;DistToCana;LRR;beach_h;beach_w;toe_dl_z;crest_dh_z;slp_sh_slo;Start_lon;Start_lat;max_z;Nourish;D_B_Constr;OldInlet;Infrastr;DistDH;DistDL;Shape_Length_1;FID_Recharge_modNov18_subset;row;column_;zone;Rech;Conc;Depth')

arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID","id_temp","dist_temp","DLow_easting","DLow_northing",elevGrid,slopeGrid])
arcpy.Delete_management(tranSplitPts + "_sort_temp")


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

fields = arcpy.ListFields(tranSplitPts) # list of fields in points

cursor = arcpy.UpdateCursor(tranSplitPts)
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
