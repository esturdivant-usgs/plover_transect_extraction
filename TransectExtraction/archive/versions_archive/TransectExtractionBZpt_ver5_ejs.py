'''
Deep dive Transect Extraction for Breezy Pt. NY
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez
email: sawyer.stippa@gmail.com; bgutierrez@usgs.gov
Date last modified: 11/23/2015

Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
'''

import arcpy, time
from math import radians, cos, asin, sin, atan2, sqrt, degrees
# Note: Run in ArcMap python window
# Turn off "auto display" in ArcMap preferences

# arcpy.GetParameterAsText(0)
############################################################################# Set environments
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extentsion
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'C:/Users/SSTIPPA/Desktop/ASIS/ASIS_2012.gdb' 	# Get workspace
arcpy.env.workspace=home= r'C:/Users/esturdivant/Documents/ArcGIS/Breezy2014_B_ejs.gdb' # ejs
#   NOTE back slash vs. fore slash

##################################### Inputs
transects = 'BreezyPt_extTransects_slim' 	# National Assessment transects-done
dhPts = 'DHigh_BP_edited' 					# Dune crest
dlPts = 'DLow_BPedited' 						# Dune toe
#slp_pts = 'SLPs'						# No longer need this: 12/6/2015: beach slope from lidar point clouds....for now we're not using MHW shoreline pts from this source.
barrierBoundary = 'BreezyBoundsPGon' 	# Barrier Boundary-done
ShorelinePts = 'SLPs' 			# Shoreline points, and has slope info.
MHW_2014_oceanside = 'Ocean_MHW_2014'
jetty_line = 'BreezyPt_jetty'           # Manually digitized jetty line from Arc's Imagery Basemap with everything projected to NAD 83 UTM 18N
shoreline = 'ShL_fromJetty_2014'        # Complete shoreline ready to become route in Pt. 2
finalinlet = 'BreezyPt_inletNETransect'
#recharge = "recharge_2008" 			# Recharge										NEED TO MAKE SURE THIS IS REMOVED
#elevGrid = 'Elev2014_MHW' 				# Elevation			Not needed here.
#slopeGrid = 'slope_2012' 			# Slope
#habitat = 'habitat_201211' 			# Habitat
extend = 6000 						# extended transects distance (m)   				REMOVE THIS I THINK
MLW = -1.3 						# Beach height adjustment (relative to MHW)...adjusted smaller by 6 cm due to KW value of 0.46 for beach face and 0.52 from backbarrier tidal datum (Atl. Beach, NY)
fill = -99999	  					# Replace Nulls with
finaltrans = 344                        # TransOrder id of transect corresponding to NE inlet (opposite of canal), saved as BreezyPt_inletNETransect
############################################# Outputs
dh10 = 'DHigh_10m' 							# DHigh within 10m
dl10 = 'DLow_10m' 							# DLow within 10m
SHL10 = 'SHLPts_10m'							# beach slope from lidar within 10m of transect
#extendedTransects = 'transects_extended' 	# Extended transects		Edited out 12/1/2015, have these already
baseName = 'trans_clip2BND' 				# Clipped transecst			NOTE: 'StartX' and 'StartY' in code are UTM XYs stored here.
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

# EXTENDED TRANSECTS
# EJS: Why are these commented out? Probably because already present in BreezyPt_extTransects
"""
# Create extended transects
arcpy.AddField_management(transects, 'LENGTH', 'LONG')
arcpy.CalculateField_management(transects, "LENGTH", extend, "Python_9.3")
arcpy.BearingDistanceToLine_management(transects, extendedTransects, "StartX", "StartY", "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))

# Join transect fields to extended transects
arcpy.JoinField_management(extendedTransects, "TransOrder", transects, "TransOrder", ["LRR","LR2","LSE","LCI90"])
"""

arcpy.DeleteField_management(transects, ['Join_Count','BaselineID','ProcTime','EndX','EndY','BASELINED','PROCTIME',
                                         'STARTX','STARTY','ENDX','ENDY','AZIMUTH','transOrder_orig','Shape_Length1'])
# EJS: drop all fields that are not in transects_extended of ASIS processing
# EJS:

# Add ID field to DH and DL and populate with OBJECTID - unique ID field needed for spatial join...12/6/2015 Added Slope from lidar shoreline files to the mix.
arcpy.AddField_management(dhPts,'ID','SINGLE')
arcpy.AddField_management(dlPts,'ID','SINGLE')
arcpy.CalculateField_management(dhPts,"ID","!OBJECTID!","Python_9.3")
#arcpy.CalculateField_management(dhPts,"ID","!FID!","Python_9.3")
arcpy.CalculateField_management(dlPts,"ID","!OBJECTID!","Python_9.3")
#arcpy.CalculateField_management(dlPts,"ID","!FID!","Python_9.3")

# Join closest DH and DL within 10m to transects (create temp)...12/6/2015 Added Slope from lidar shoreline files to the mix.
arcpy.SpatialJoin_analysis(transects,dhPts,'dh_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.SpatialJoin_analysis(transects,dlPts,'dl_trans_temp','#','#','#',"CLOSEST","10 meters")

# Join transects back to DH and DL..12/3/2015 Added Slope from lidar shoreline files to the mix.
arcpy.AddJoin_management(dhPts,"ID",'dh_trans_temp',"ID","KEEP_COMMON")
arcpy.AddJoin_management(dlPts,"ID",'dl_trans_temp',"ID","KEEP_COMMON")

# Save only the DH and DL that are within 10m as new layers...12/3/2015 Added Slope from lidar shoreline files to the mix.
arcpy.CopyFeatures_management(dhPts, dh10)
arcpy.CopyFeatures_management(dlPts, dl10)


# Remove Join...12/3/2015 Added Slope from lidar shoreline files to the mix.
arcpy.RemoveJoin_management(dhPts)
arcpy.RemoveJoin_management(dlPts)


# Join DH fields to transects
arcpy.AddField_management(transects, 'DH_Lon', 'DOUBLE')
arcpy.AddField_management(transects, 'DH_Lat', 'DOUBLE')
arcpy.AddField_management(transects, 'DH_easting', 'DOUBLE')
arcpy.AddField_management(transects, 'DH_northing', 'DOUBLE')
arcpy.AddField_management(transects, 'DH_z', 'DOUBLE')

arcpy.JoinField_management(transects, "TransOrder", 'dh_trans_temp', "TransOrder", ["lon_sm", "lat_sm", "east_sm", "north_sm", "dhigh_z", ])
arcpy.CalculateField_management(transects, "DH_Lon", "!lon_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DH_Lat", "!lat_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DH_easting", "!east_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DH_northing", "!north_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DH_z", "!dhigh_z!", "Python_9.3")

arcpy.DeleteField_management(transects, "lon_sm")
arcpy.DeleteField_management(transects, "lat_sm")
arcpy.DeleteField_management(transects, "east_sm")
arcpy.DeleteField_management(transects, "north_sm")
arcpy.DeleteField_management(transects, "dhigh_z")
arcpy.DeleteField_management(transects, "Azimuth")
#arcpy.DeleteField_management(transects, "SHAPE_Length")

arcpy.Delete_management("dh_trans_temp")

# DL fields
arcpy.AddField_management(transects, 'DL_Lon', 'DOUBLE')
arcpy.AddField_management(transects, 'DL_Lat', 'DOUBLE')
arcpy.AddField_management(transects, 'DL_easting', 'DOUBLE')
arcpy.AddField_management(transects, 'DL_northing', 'DOUBLE')
arcpy.AddField_management(transects, 'DL_z', 'DOUBLE')

arcpy.JoinField_management(transects, "TransOrder", 'dl_trans_temp', "TransOrder", ["lon_sm", "lat_sm", "east_sm", "north_sm", "dlow_z", ])
arcpy.CalculateField_management(transects, "DL_Lon", "!lon_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DL_Lat", "!lat_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DL_easting", "!east_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DL_northing", "!north_sm!", "Python_9.3")
arcpy.CalculateField_management(transects, "DL_z", "!dlow_z!", "Python_9.3")

arcpy.DeleteField_management(transects, "lon_sm")
arcpy.DeleteField_management(transects, "lat_sm")
arcpy.DeleteField_management(transects, "east_sm")
arcpy.DeleteField_management(transects, "north_sm")
arcpy.DeleteField_management(transects, "dlow_z")
#arcpy.DeleteField_management(transects, "Azimuth")
#arcpy.DeleteField_management(transects, "SHAPE_Length")

arcpy.Delete_management("dl_trans_temp")
"""
Experimentally moving to Pt. 4
# ShorelinePts fields
arcpy.AddField_management(transects, 'ShL_Lon', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_Lat', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_easting', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_northing', 'DOUBLE')
arcpy.AddField_management(transects, 'Bslope', 'DOUBLE')

arcpy.JoinField_management(transects, "TransOrder", 'SHL_trans_temp', "TransOrder", ["SL_Lon", "SL_Lat", "easting", "northing", "slope"])
arcpy.CalculateField_management(transects, "ShL_Lon", "!SL_Lon!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_Lat", "!SL_Lat!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_easting", "!easting!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_northing", "!northing!", "Python_9.3")
arcpy.CalculateField_management(transects, "Bslope", "!slope!", "Python_9.3")

arcpy.DeleteField_management(transects, "SL_Lon")
arcpy.DeleteField_management(transects, "SL_Lat")
arcpy.DeleteField_management(transects, "easting")
arcpy.DeleteField_management(transects, "northing")
arcpy.DeleteField_management(transects, "slope")

arcpy.Delete_management("SHL_trans_temp")
"""
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
arcpy.Clip_analysis(transects, barrierBoundary, baseName)

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
"""
Moved to Pt. 4
# Calc DistDH and DistDL
# EJS: replaced StartX with ShL_easting and StartY with ShL_northing to measure dist from MHW (instead of transect start
# Potentially could have stayed StartX and StartY because the transects have already been clipp
arcpy.AddField_management(baseName, "DistDH", "DOUBLE")
arcpy.AddField_management(baseName, "DistDL", "DOUBLE")
arcpy.CalculateField_management(baseName, "DistDH",'math.sqrt((!ShL_easting! - !DH_easting!) * (!ShL_easting! - !DH_easting!) + (!DH_northing! - !ShL_northing!) * (!DH_northing! - !ShL_northing!))',"PYTHON", '#')
arcpy.CalculateField_management(baseName, "DistDL",'math.sqrt((!ShL_easting! - !DL_easting!) * (!ShL_easting! - !DL_easting!) + (!DL_northing! - !ShL_northing!) * (!DL_northing! - !ShL_northing!))',"PYTHON", '#')
"""
# Remove temp files
arcpy.Delete_management(baseName + "_length_temp")
arcpy.Delete_management(baseName + "_trans_temp")
arcpy.Delete_management(baseName + "_verts_temp")

# EJS: completely reworked
# Calc dist from canal
"""
Canal point: intersect center of the jetty with MHW shoreline extended through jetty (southernmost jetty on Breezy Pt):
  visually pick the point from imagery beneath the shoreline layers, best approximation
  either a) create a line file as a reference or b) build the coordinates into the code.
  Sites without jetty: use nearest intersect of transect-MHW shoreline that is just seaward of the barrier beach according to imagery of that year.
"""
# Create shoreline if it does not already exist
if arcpy.Exists(shoreline) == 0:
    # Create oceanside line that begins at jetty (canalPt) = 'shoreline'
    arcpy.Select_analysis(baseName,'trans_canalline_temp','OBJECTID=1')
    arcpy.Intersect_analysis(['trans_canalline_temp',MHW_2014_oceanside],'trans_canalpt_temp',"ONLY_FID",'1 METERS','POINT')
    arcpy.SplitLineAtPoint_management(MHW_2014_oceanside,'trans_canalpt_temp','Ocean_split_temp','1 Meters')
    arcpy.MultipartToSinglepart_management("Ocean_split_temp", "Ocean_split_temp_singlepart")
    arcpy.Sort_management('Ocean_split_temp_singlepart','ocean_split_sorted_temp','Shape','UR')
    arcpy.Select_analysis('ocean_split_sorted_temp','shoreline_temp','OBJECTID=1')  # can't be condensed with below: eliminate additional segments that prevent line from extending
    arcpy.Merge_management(['shoreline_temp',jetty_line],'shoreline_jetty_merge')
    arcpy.ExtendLine_edit('shoreline_jetty_merge','250 Meters')
    arcpy.Sort_management('shoreline_jetty_merge','shorejetty_sorted','Shape','UR')
    arcpy.Select_analysis('shorejetty_sorted',shoreline,'OBJECTID=1')


# Convert shoreline to Polyline M, find intersection points with transects, create distance table, and join distance measurements to baseName
arcpy.CreateRoutes_lr(shoreline,"Id","shoreline_route_temp","LENGTH")
arcpy.Intersect_analysis([baseName,"shoreline_route_temp"],'intersectPts',"ALL",'1 METERS','POINT') # alt: only FID, possible because later joining straight back
arcpy.LocateFeaturesAlongRoutes_lr('intersectPts',"shoreline_route_temp", 'Id', '1 Meters',"DistToCana_temp",'RID POINT MEAS')
arcpy.JoinField_management(baseName, "TransOrder", "DistToCana_temp","TransOrder", "MEAS")

# Tidy up
arcpy.AddField_management(baseName, "DistToCana",'DOUBLE')
arcpy.CalculateField_management(baseName, "DistToCana", "!MEAS!", "PYTHON") # Change back to MEAS
arcpy.DeleteField_management(baseName, "MEAS")
# Delete temp files
arcpy.Delete_management('trans_canalline_temp')
arcpy.Delete_management('trans_canalpt_temp')
arcpy.Delete_management('Ocean_split_temp')
arcpy.Delete_management('Ocean_split_temp_singlepart')
arcpy.Delete_management('ocean_split_sorted_temp')
arcpy.Delete_management('shoreline_temp')
arcpy.Delete_management('shoreline_jetty_merge')
arcpy.Delete_management('shorejetty_sorted')
arcpy.Delete_management("shoreline_route_temp")
arcpy.Delete_management("DistToCana_temp")

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

#Was in Pt 1 so that values would be preserved even if Clip segmented transects; actually, probably doesn't matter because clip creates multipart features
arcpy.AddField_management(ShorelinePts,'ID','SINGLE')
arcpy.CalculateField_management(ShorelinePts,"ID","!OBJECTID!","Python_9.3")
arcpy.SpatialJoin_analysis(transects,ShorelinePts,'SHL_trans_temp','#','#','#',"CLOSEST","10 meters") # 10 meters here, but in SSorig, this isn't included
arcpy.AddJoin_management(ShorelinePts,"ID",'SHL_trans_temp',"ID","KEEP_COMMON")
arcpy.CopyFeatures_management(ShorelinePts, SHL10)
arcpy.RemoveJoin_management(ShorelinePts)

# ShorelinePts fields
arcpy.AddField_management(transects, 'ShL_Lon', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_Lat', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_easting', 'DOUBLE')
arcpy.AddField_management(transects, 'ShL_northing', 'DOUBLE')
arcpy.AddField_management(transects, 'Bslope', 'DOUBLE')

arcpy.JoinField_management(transects, "TransOrder", 'SHL_trans_temp', "TransOrder", ["SL_Lon", "SL_Lat", "easting", "northing", "slope"]) # SSorig joined sl_x and slope, not easting&northing
arcpy.CalculateField_management(transects, "ShL_Lon", "!SL_Lon!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_Lat", "!SL_Lat!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_easting", "!easting!", "Python_9.3")
arcpy.CalculateField_management(transects, "ShL_northing", "!northing!", "Python_9.3")
arcpy.CalculateField_management(transects, "Bslope", "!slope!", "Python_9.3")

arcpy.DeleteField_management(transects, "SL_Lon")
arcpy.DeleteField_management(transects, "SL_Lat")
arcpy.DeleteField_management(transects, "easting")
arcpy.DeleteField_management(transects, "northing")
arcpy.DeleteField_management(transects, "slope")

arcpy.Delete_management("SHL_trans_temp")

# Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
arcpy.AddField_management(baseName, "DistDH", "DOUBLE")
arcpy.AddField_management(baseName, "DistDL", "DOUBLE")
arcpy.CalculateField_management(baseName, "DistDH",'math.sqrt((!ShL_easting! - !DH_easting!) * (!ShL_easting! - !DH_easting!) + (!DH_northing! - !ShL_northing!) * (!DH_northing! - !ShL_northing!))',"PYTHON", '#')
arcpy.CalculateField_management(baseName, "DistDL",'math.sqrt((!ShL_easting! - !DL_easting!) * (!ShL_easting! - !DL_easting!) + (!DL_northing! - !ShL_northing!) * (!DL_northing! - !ShL_northing!))',"PYTHON", '#')

"""
Already happened in Part 1, where it may be better to associate values with entire (pre-clipped) transect (or may not since clip preserves multipart features
# Add Lon Lat Fields to shorelinePts......
# EJS: In SLPs currently, there are SL_Lon, SL_Lat, ShL_Lon2, and ShL_Lat2. The pairs are identical.; commented out below
# EJS: operation below adds Bslope field (from somewhere...)
arcpy.AddField_management(ShorelinePts, 'ShL_Lon2', 'DOUBLE')
arcpy.AddField_management(ShorelinePts, 'ShL_Lat2', 'DOUBLE')
arcpy.CalculateField_management(ShorelinePts, 'ShL_Lon2', '!SL_Lon!', 'Python_9.3', '#')
arcpy.CalculateField_management(ShorelinePts, 'ShL_Lat2', '!SL_Lat!', 'Python_9.3', '#')
arcpy.DeleteField_management(ShorelinePts,['ShL_Lat','ShL_Lat'])

# Join Transects with closest shorelinePts
arcpy.SpatialJoin_analysis(baseName,ShorelinePts,'trans_temp', '#', '#', '#', "CLOSEST")
arcpy.JoinField_management(baseName, "TransOrder", 'trans_temp', "TransOrder", ["slope", "ShL_Lon2", "ShL_Lat2"])
# BSlope is all Null
"""

# EJS: Calc DL and DH height above MHW
arcpy.AddField_management(baseName, 'DL_zMHW', 'DOUBLE')
arcpy.AddField_management(baseName, 'DH_zMHW', 'DOUBLE')
arcpy.CalculateField_management(baseName, 'DL_zMHW','!DL_z!-0.46',"PYTHON",'#')
arcpy.CalculateField_management(baseName, 'DH_zMHW','!DH_z!-0.46',"PYTHON",'#')

# EJS: Prepare to calculate additional beach parameters
arcpy.AddField_management(baseName, 'beach_h_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'beach_h_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'delta_xm_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'delta_x_gc_MLW', 'DOUBLE')
arcpy.AddField_management(baseName, 'azimuth_SL', 'DOUBLE')
arcpy.AddField_management(baseName, 'MLW_Lon', 'DOUBLE')
arcpy.AddField_management(baseName, 'MLW_Lat', 'DOUBLE')
arcpy.AddField_management(baseName, 'beachWidth_MLW', 'DOUBLE')

# Calculate MHW and MLW position and beach width
# EJS: Ben says these seem to populate well
cursor = arcpy.UpdateCursor(baseName)
for row in cursor:
    skip = 0
    # Calculate Beach height from MHW and MLW
    # if dune toe is missing or bogus, use dhigh instead
    if row.getValue('DL_z') is not None:
        lon1 = radians(row.getValue('DL_Lon'))
        lat1 = radians(row.getValue('DL_Lat'))
        row.setValue('beach_h_MLW', row.getValue('DL_z')- MLW)
    elif (row.getValue('DL_z') is None) and (row.getValue('DH_z') is not None) and (row.getValue('DH_z') < 2.5):
        lon1 = radians(row.getValue('DH_Lon'))
        lat1 = radians(row.getValue('DH_Lat'))
        row.setValue('beach_h_MLW', row.getValue('DH_z') - (MLW))
    else:
        skip = 1

    if skip == 0:
        # Calculate Euclidean distance between dune and MHW Shoreline
        # EJS: doesn't like '/' ?
        row.setValue('delta_xm_MLW', abs(row.getValue('beach_h_MLW')/row.getValue('Bslope')))    # modified with 'Bslope' on 12/3/2015

        # Convert chord distance to Angular distance along great circle (gc)
        r = 6371 # Radius of earth in meters
        mlwKM = row.getValue('delta_xm_MLW')/1000			#deal in units of KM vs. M
        d2 = 2 * asin(mlwKM/(2*r))
        row.setValue('delta_x_gc_MLW', d2)

        # Find Azimuth between dune and MHW shoreline
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

        # Calculate Position of MLW shoreline
        latMLW = asin((sin(lat2) * cos(d2)) + (cos(lat2) * sin(d2) * cos(phiR)))
        lonMLW = lon2 + atan2(sin(phiR)*sin(d2)*cos(lat2), cos(d2)-sin(lat2)*sin(latMLW))
        row.setValue('MLW_Lat', degrees(latMLW))
        row.setValue('MLW_Lon', degrees(lonMLW))

        # Calculate beach width from dune to MLW shoreline
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

   /\\\\\\\\\\\\\      /\\\\\\\\\       /\\\\\\\\\       /\\\\\\\\\\\\\\\                      /\\\\\
   \/\\\/////////\\\   /\\\\\\\\\\\\\   /\\\///////\\\   \///////\\\/////                   /\\\\////
    \/\\\       \/\\\  /\\\/////////\\\ \/\\\     \/\\\         \/\\\                      /\\\///
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
#arcpy.AddMessage("Starting Part 6")
#startPart6 = time.clock()

#fields = arcpy.ListFields(tranSplitPts) # list of fields in points

#cursor = arcpy.UpdateCursor(tranSplitPts)
#for row in cursor:
#    for field in fields:
#        if row.getValue(field.name) is None:
#            row.setValue(field.name,fill)
#            cursor.updateRow(row)
#        else:
#            pass

#endPart6 = time.clock()
#duration = endPart6 - startPart6
#hours, remainder = divmod(duration, 3600)
#minutes, seconds = divmod(remainder, 60)
#print "Part 6 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

#end = time.clock()
#duration = end - start
#hours, remainder = divmod(duration, 3600)
#minutes, seconds = divmod(remainder, 60)
#print "Processing completed in %dh:%dm:%fs" % (hours, minutes, seconds)