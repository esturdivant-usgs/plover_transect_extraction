'''
Deep dive Transect Extraction for Fire Island, NY 2012
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 1/25/2016

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''

import arcpy, time, os
from math import radians, cos, asin, sin, atan2, sqrt, degrees

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
############ Inputs #########################
# Year-specific:
arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\FireIsland2014.gdb"
year = '2014'
barrierBoundary = 'FI_BNDpoly_'+year 	# Barrier Boundary polygon; create with TE_createBoundaryPolygon.py
dhPts = 'FI_DHpts_2014_edited' 					# Dune crest,***NOTE: replace -99999 values with Null before running!!!
dlPts = 'FI_DLpts_2014_edited' 						# Dune toe,  ***NOTE: replace -99999 values with Null before running!!!
ShorelinePts = 'FI_SLPs_'+year 			# Shoreline points
MHW_oceanside = 'FI_FullShoreline_2014_edited2_inlet'   # MHW, used to create BreezyBoundsPGon
inletLines = 'FI_inletLines_'+year
elevGrid = 'FI_lidar1m_'+year				# Elevation
slopeGrid = 'FI_slope_'+year
#habitat = 'habitat_201211' 			# Habitat

#  Site-specific:
site = 'FI'
extendedTransects = 'FI_extTransects_edit3' # Created MANUALLY: see TransExtv4Notes.txt
#rawtransects = 'LongIsland_LT' 	# National Assessment transects-done
#extend = 2000 						# extended transects distance (m) IF NEEDED
#jetty_line = 'FireIslandInlet'           # Manually digitized jetty line from Arc's Imagery Basemap with everything projected to NAD 83 UTM 18N
#finalinlet = 'NEInletTransect' # transect corresponding to NE inlet (opposite of canal)
MLW = -1.27 						# Beach height adjustment (relative to MHW)...adjusted smaller by 6 cm due to KW value of 0.46 for beach face and 0.52 from backbarrier tidal datum (Atl. Beach, NY)
fill = -99999	  					# Replace Nulls with
dMHW = -.46
############## Outputs ###############################
dh10 = site+'_DHigh_10m_'+year 							# DHigh within 10m
dl10 = site+'_DLow_10m_'+year						# DLow within 10m
SHL10 = site+'_SHLPts_10m_'+year							# beach slope from lidar within 10m of transect
shoreline = site+'_ShoreBetweenInlets_'+year        # Complete shoreline ready to become route in Pt. 2
baseName = 'trans_clip_working'         # Clipped transects			NOTE: 'StartX' and 'StartY' in code are UTM XYs stored here.
transects_final = site+'_'+year+'populatedTransects'

tranSin = site + '_trans_SinglePart' 				# Single part transects
tranSplit = site + '_trans_5mSeg' 			# Transect Segments (5m)
tranSplitPts = site + '_trans_5mSegPts' 	# Outputs Transect Segment points
transSplitPts_final = site+year+'_trans_5mSegPts'

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
Requires DH, DL, and SHL points, NA transects
'''
print "Starting Part 1"
startPart1 = time.clock()

# Extend transects if not already
if arcpy.Exists(extendedTransects) == 0:
    arcpy.AddField_management(rawtransects, 'LENGTH', 'LONG') # Add extended length field
    arcpy.CalculateField_management(rawtransects, "LENGTH", extend, "Python_9.3") # populate with legnth
    arcpy.BearingDistanceToLine_management(rawtransects, extendedTransects, "StartX", "StartY",  # Create extended transects
        "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))
    arcpy.JoinField_management(extendedTransects, "TransOrder", rawtransects, "TransOrder", ["LRR","LR2","LSE","LCI90"]) # Join transect fields to extended transects

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
transwork = extendedTransects + '_' + year
arcpy.Sort_management(extendedTransects,transwork,'TRANSORDER')
extendedTransects = transwork

# Replace fill values with Null and populate ID with OBJECTID
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

def BeachPointMetricsToTransects(transects,oldPts,newPts,geofields,ptfields):
    # Save only points within 10m of transect and join beach point metrics to transects
    arcpy.AddField_management(oldPts,'ID','SINGLE')
    with arcpy.da.UpdateCursor(oldPts, ("ID","OBJECTID")) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.SpatialJoin_analysis(transects,oldPts, 'trans_temp','#','#','#',"CLOSEST","10 meters")
    arcpy.AddJoin_management(oldPts,"ID", 'trans_temp',"ID","KEEP_COMMON")
    arcpy.CopyFeatures_management(oldPts, newPts)
    arcpy.RemoveJoin_management(oldPts)
    arcpy.JoinField_management(transects, "TransOrder", 'trans_temp', "TransOrder", geofields)
    for i in range(len(geofields)):
        arcpy.AddField_management(transects, ptfields[i], 'DOUBLE')
        with arcpy.da.UpdateCursor(transects, geofields[i] + ptfields[i]) as cursor:
            for row in cursor:
                row[0] = row[1]
                cursor.updateRow(row)
        arcpy.DeleteField_management(transects, geofields[i])
    arcpy.Delete_management(os.path.join(home,'trans_temp'))

# Call function to join DH, DL, and Shoreline metrics to transects
geofields = ['lon_sm', 'lat_sm', 'east_sm', 'north_sm', 'dhigh_z']
DHfields = ['DH_Lon','DH_Lat','DH_easting','DH_northing','DH_z']
BeachPointMetricsToTransects(extendedTransects,dhPts,dh10,geofields,DHfields)
geofields[4] = "dlow_z"
DLfields = ['DL_Lon','DL_Lat','DL_easting','DL_northing','DL_z']
BeachPointMetricsToTransects(extendedTransects,dlPts,dl10,geofields,DLfields)
geofields[4] = "slope"
ShLfields = ['ShL_Lon','ShL_Lat','ShL_easting','ShL_northing', 'Bslope']
BeachPointMetricsToTransects(extendedTransects,ShorelinePts,SHL10,geofields,ShLfields)

# Add ID field to DH and DL and populate with OBJECTID
#arcpy.AddField_management(dhPts,'ID','SINGLE')
#arcpy.AddField_management(dlPts,'ID','SINGLE')
#arcpy.AddField_management(ShorelinePts,'ID','SINGLE')
#arcpy.CalculateField_management(dhPts,"ID","!OBJECTID!","Python_9.3")
#arcpy.CalculateField_management(dlPts,"ID","!OBJECTID!","Python_9.3")
#arcpy.CalculateField_management(ShorelinePts,"ID","!OBJECTID!","Python_9.3")

"""
# Join closest DH and DL within 10m to transects (create temp), join transects back, and save only those pts within 10m of transects
arcpy.SpatialJoin_analysis(extendedTransects,dhPts,'dh_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.SpatialJoin_analysis(extendedTransects,dlPts,'dl_trans_temp','#','#','#',"CLOSEST","10 meters")
arcpy.SpatialJoin_analysis(extendedTransects,ShorelinePts,'SHL_trans_temp','#','#','#',"CLOSEST","10 meters") # 10 meters here, but in SSorig, this isn't included
arcpy.AddJoin_management(dhPts,"ID",'dh_trans_temp',"ID","KEEP_COMMON")
arcpy.AddJoin_management(dlPts,"ID",'dl_trans_temp',"ID","KEEP_COMMON")
arcpy.AddJoin_management(ShorelinePts,"ID",'SHL_trans_temp',"ID","KEEP_COMMON")
arcpy.CopyFeatures_management(dhPts, dh10)
arcpy.CopyFeatures_management(dlPts, dl10)
arcpy.CopyFeatures_management(ShorelinePts, SHL10)
arcpy.RemoveJoin_management(dhPts)
arcpy.RemoveJoin_management(dlPts)
arcpy.RemoveJoin_management(ShorelinePts)

# Geo fields for dune points:
geofields = ['lon_sm', 'lat_sm', 'east_sm', 'north_sm', 'dhigh_z']
DHfields = ['DH_Lon','DH_Lat','DH_easting','DH_northing','DH_z']
DLfields = ['DL_Lon','DL_Lat','DL_easting','DL_northing','DL_z']
ShLfields = ['ShL_Lon','ShL_Lat','ShL_easting','ShL_northing', 'Bslope']

# Join DH fields to transects
arcpy.JoinField_management(extendedTransects, "TransOrder", 'dh_trans_temp', "TransOrder", geofields)
for i in range(len(geofields)):
    #DH
    arcpy.AddField_management(extendedTransects, DHfields[i], 'DOUBLE')
    with arcpy.da.UpdateCursor(extendedTransects, geofields[i] + DHfields[i]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.DeleteField_management(extendedTransects, geofields[i])
arcpy.Delete_management(os.path.join(home,"dh_trans_temp"))

# Join DL fields to transects
geofields[4] = "dlow_z"
arcpy.JoinField_management(extendedTransects, "TransOrder", 'dl_trans_temp', "TransOrder", geofields)
for i in range(len(geofields)):
    arcpy.AddField_management(extendedTransects, DLfields[i], 'DOUBLE')
    with arcpy.da.UpdateCursor(extendedTransects, geofields[i] + DLfields[i]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.DeleteField_management(extendedTransects, geofields[i])
arcpy.Delete_management(os.path.join(home,"dl_trans_temp"))

geofields[4] = "slope"
arcpy.JoinField_management(extendedTransects, "TransOrder", 'SHL_trans_temp', "TransOrder", geofields)
for i in range(len(geofields)):
    arcpy.AddField_management(extendedTransects, ShLfields[i], 'DOUBLE')
    with arcpy.da.UpdateCursor(extendedTransects, geofields[i] + ShLfields[i]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.DeleteField_management(extendedTransects, geofields[i])
arcpy.Delete_management(os.path.join(home,"SHL_trans_temp"))
"""
# Replaced below with above for efficiency
"""
# DH fields
arcpy.AddField_management(extendedTransects, 'DH_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DH_z', 'DOUBLE')

arcpy.JoinField_management(extendedTransects, "TransOrder", 'dh_trans_temp', "TransOrder", geofields)

arcpy.CalculateField_management(extendedTransects, "DH_Lon", "!lon_sm!", "Python_9.3") # Changed fieldname from lon to lon_sm
arcpy.CalculateField_management(extendedTransects, "DH_Lat", "!lat_sm!", "Python_9.3") # Changed fieldname from lon to lon_sm
arcpy.CalculateField_management(extendedTransects, "DH_easting", "!east_sm!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_northing", "!north_sm!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DH_z", "!dhigh_z!", "Python_9.3")

arcpy.DeleteField_management(extendedTransects, lonfield)  # Changed fieldname from lon to lon_sm
arcpy.DeleteField_management(extendedTransects, latfield) # Changed fieldname from lon to lon_sm
arcpy.DeleteField_management(extendedTransects, eastingfield)
arcpy.DeleteField_management(extendedTransects, northingfield)
arcpy.DeleteField_management(extendedTransects, "dhigh_z")

arcpy.Delete_management(os.path.join(home,"dh_trans_temp"))

# DL fields
arcpy.AddField_management(extendedTransects, 'DL_Lon', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_Lat', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_easting', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_northing', 'DOUBLE')
arcpy.AddField_management(extendedTransects, 'DL_z', 'DOUBLE')

arcpy.JoinField_management(extendedTransects, "TransOrder", 'dl_trans_temp', "TransOrder", [lonfield, latfield, eastingfield, northingfield, "dlow_z", ])

arcpy.CalculateField_management(extendedTransects, "DL_Lon", "!lon_sm!", "Python_9.3") # Changed fieldname from lon to lon_sm
arcpy.CalculateField_management(extendedTransects, "DL_Lat", "!lat_sm!", "Python_9.3") # Changed fieldname from lon to lon_sm
arcpy.CalculateField_management(extendedTransects, "DL_easting", "!east_sm!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_northing", "!north_sm!", "Python_9.3")
arcpy.CalculateField_management(extendedTransects, "DL_z", "!dlow_z!", "Python_9.3")

arcpy.DeleteField_management(extendedTransects, lonfield) # Changed fieldname from lon to lon_sm
arcpy.DeleteField_management(extendedTransects, latfield) # Changed fieldname from lon to lon_sm
arcpy.DeleteField_management(extendedTransects, eastingfield)
arcpy.DeleteField_management(extendedTransects, northingfield)
arcpy.DeleteField_management(extendedTransects, "dlow_z")

arcpy.Delete_management(os.path.join(home,"dl_trans_temp"))

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
#arcpy.CalculateField_management(baseName, "DistDH",'math.sqrt((!ShL_easting! - !DH_easting!) * (!ShL_easting! - !DH_easting!) + (!DH_northing! - !ShL_northing!) * (!DH_northing! - !ShL_northing!))',"PYTHON", '#')
#arcpy.CalculateField_management(baseName, "DistDL",'math.sqrt((!ShL_easting! - !DL_easting!) * (!ShL_easting! - !DL_easting!) + (!DL_northing! - !ShL_northing!) * (!DL_northing! - !ShL_northing!))',"PYTHON", '#')
with arcpy.da.UpdateCursor(baseName, "*") as cursor:
    for row in cursor:
        try:
            row.DistDH = math.sqrt((row.ShL_easting - row.DH_easting)**2 + (row.DH_northing - row.ShL_northing)**2)
        except:
            pass
        try:
            row.DistDL = math.sqrt((row.ShL_easting - row.DL_easting)**2 + (row.DL_northing - row.ShL_northing)**2)
        except:
            pass
        cursor.updateRow(row)

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
    arcpy.Intersect_analysis([inletLines,MHW_oceanside],'xpts_createroute','ONLY_FID',output_type='POINT') # temp1_pts
    arcpy.SplitLineAtPoint_management(MHW_oceanside,'xpts_createroute','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", ShorelinePts,'1 METERS')
    arcpy.CopyFeatures_management('split_temp',shoreline)

    arcpy.AddField_management(shoreline,"ORIG_FID","SHORT")
    arcpy.CalculateField_management(shoreline,"ORIG_FID","!OBJECTID!","PYTHON")

    #arcpy.MultipartToSinglepart_management("split_temp", "Ocean_split_temp_singlepart")
    #arcpy.Select_analysis('Ocean_split_temp_singlepart',shoreline+'_temp','Shape_Length >0.01')
    # Eliminate bayside line, if it is present (does MHW_oceanside need to include bayside shore in current version?) based on presence of SHLpts
    #arcpy.SelectLayerByLocation_management(shoreline+'_temp',"INTERSECT", ShorelinePts)
    #arcpy.CopyFeatures_management('split_temp',shoreline)

    # Extend shoreline beyond end of boundary polygon because end of polygon is not equivalent to inlet
    #arcpy.AddField_management(shoreline+'_temp', 'LENGTH', 'LONG')
    #arcpy.SelectLayerByAttribute_management("ShoreBetweenInlets_2014_temp","NEW_SELECTION",'"OBJECTID"=4')
    #arcpy.CalculateField_management(shoreline+'_temp', "LENGTH", 80000, "Python_9.3")
    #arcpy.BearingDistanceToLine_management(shoreline+'_temp', shoreline, "StartX", "StartY", "LENGTH","METERS", "Azimuth", "DEGREES", "GEODESIC",'TransOrder',arcpy.SpatialReference(26918))

    # Merge and then extend shoreline to inlet lines
    #arcpy.Merge_management(['shoreline_temp',jetty_line,finalinlet],shoreline)
    #arcpy.ExtendLine_edit(shoreline,'250 Meters')
    #arcpy.TrimLine_edit(shoreline, dangle_length="3100 Meters", delete_shorts="DELETE_SHORT") ### NEW = check
    # Remove temp files
    #arcpy.Delete_management(os.path.join(home,'trans_canalline_temp'))
    arcpy.Delete_management(os.path.join(home,'xpts_createroute'))
    arcpy.Delete_management(os.path.join(home,'split_temp'))

else:
    pass

# Convert shoreline to routes
arcpy.CreateRoutes_lr(shoreline,"OBJECTID","shore_routeLL_temp","LENGTH",coordinate_priority='LOWER_LEFT')
arcpy.SelectLayerByAttribute_management(shoreline,"NEW_SELECTION",'"OBJECTID"<4')
arcpy.CreateRoutes_lr(shoreline,"ORIG_FID","shore_routeUR_temp","LENGTH",coordinate_priority='UPPER_RIGHT')
arcpy.SelectLayerByAttribute_management(shoreline,"CLEAR_SELECTION")

# Measure distance from inlet to each transect in both directions
arcpy.Intersect_analysis([baseName,'shore_routeLL_temp'],'xpts','ONLY_FID','1 METERS','POINT')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeUR_temp", 'ORIG_FID', '1 Meters',"DistTableUR",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.LocateFeaturesAlongRoutes_lr('xpts',"shore_routeLL_temp", 'ORIG_FID', '1 Meters',"DistTableLL",'RID POINT MEAS',distance_field='NO_DISTANCE')
arcpy.JoinField_management(baseName, "OBJECTID", 'DistTableUR',"FID_"+baseName, "MEAS")
arcpy.JoinField_management(baseName, "OBJECTID", 'DistTableLL',"FID_"+baseName, "MEAS")
arcpy.AddField_management(baseName, "Dist2Inlet",'DOUBLE')

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
arcpy.DeleteField_management(baseName, ["MEAS", "MEAS_1"])
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
# Cursor is much faster than CalculateField
with arcpy.da.UpdateCursor(baseName, ('DL_z','DH_z','DL_zMHW', 'DH_zMHW')) as cursor:
    for row in cursor:
        try:
            row[2] = row[0] + dMHW
        except:
            row[2] = None
        try:
            row[3] = row[1] + dMHW
        except:
            row[3] = None
        cursor.updateRow(row)
#arcpy.CalculateField_management(baseName, 'DL_zMHW','!DL_z!' + str(dMHW),"PYTHON",'#')
#arcpy.CalculateField_management(baseName, 'DH_zMHW','!DH_z!' + str(dMHW),"PYTHON",'#')

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

# Convert Multipart transects to individual parts

# Split transects into segments
input = home + '/' + tranSin
output = home + '/' + tranSplit
transPts_presort = 'trans_5m_segpoints_presort_temp'

# Convert transects to 5m points: multi to single; split lines; segments to center points
arcpy.MultipartToSinglepart_management(baseName, tranSin)
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx")
arcpy.XToolsGP_SplitPolylines_xtp(input,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
arcpy.FeatureToPoint_management(tranSplit,transPts_presort)

# Add xy for each segment center point
arcpy.AddField_management(transPts_presort,"seg_x", "DOUBLE")
arcpy.AddField_management(transPts_presort,"seg_y", "DOUBLE")
arcpy.AddField_management(transPts_presort,"Dist_Seg","DOUBLE")
arcpy.AddField_management(transPts_presort,"id_temp","TEXT")

# Get transect start xy and calc dist_seg (dist from MHW oceanside)
# Calc Field - 43 seconds; cursor - 5.25 seconds
with arcpy.da.UpdateCursor(transPts_presort, ("SHAPE@X", "SHAPE@Y", "seg_x", "seg_y")) as cursor:
    for row in cursor:
        row[2] = row[0]
        row[3] = row[1]
        cursor.updateRow(row)
# Calc Field took 8.9 seconds; UpdateCursor takes 3.5 seconds
with arcpy.da.UpdateCursor(transPts_presort, "*") as cursor:
    for row in cursor:
        try:
            row.Dist_Seg = math.sqrt((row.seg_x -row.ShL_easting)**2 + (row.seg_y - row.ShL_northing)**2)
            cursor.updateRow(row)
        except:
            pass

#Create unique id SplitSort by sorting on TransOrder and DistSeg # Create temp file with points sorted by [TRANSORDER]_[Dist_Seg]
# Calc field - 24 seconds; cursor - 4.5 seconds
with arcpy.da.UpdateCursor(transPts_presort, ('TRANSORDER','Dist_Seg','id_temp')) as cursor:
    for row in cursor:
        try:
            dist = str(int(row[1]))
        except:
            dist = 'Null'
        row[2] = "%s_%s" % (str(row[0]), dist)
        cursor.updateRow(row)

# Sort on TransOrder and DistSeg
arcpy.Sort_management(transPts_presort, tranSplitPts, 'TransOrder ASCENDING;Dist_Seg ASCENDING')

# Could add fields based on list and for loop; then use the same loop in the cursor loop
arcpy.AddField_management(tranSplitPts,"SplitSort","LONG")
arcpy.AddField_management(tranSplitPts,"DistSegDH","DOUBLE")
arcpy.AddField_management(tranSplitPts,"DistSegDL","DOUBLE")
arcpy.AddField_management(tranSplitPts,"PointZ","DOUBLE")
arcpy.AddField_management(tranSplitPts,"PointSlp","DOUBLE")

with arcpy.da.UpdateCursor(tranSplitPts, ('SplitSort','OBJECTID','Dist_Seg','DistDH','DistDL','DistSegDH','DistSegDL')) as cursor:
    for row in cursor:
        row[0] = row[1]
        try:
            row[5] = row[2]-row[3]
        except:
            pass
        try:
            row[6] = row[2]-row[4]
        except:
            pass
        cursor.updateRow(row)

# Create slope grid if doesn't already exist
if arcpy.Exists(slopeGrid) == 0:
    arcpy.Slope_3d(elevGrid,slopeGrid,'PERCENT_RISE')

#Get elevation and slope at points ### TAKES A WHILE?
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,elevGrid) # duration: 3 min 20 sec
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,slopeGrid)
with arcpy.da.UpdateCursor(tranSplitPts, ("PointZ", elevGrid,"PointSlp", slopeGrid)) as cursor:
    for row in cursor:
        row[0] = row[1]
        row[2] = row[3]
        cursor.updateRow(row)

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
arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID","id_temp",elevGrid,slopeGrid])
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
