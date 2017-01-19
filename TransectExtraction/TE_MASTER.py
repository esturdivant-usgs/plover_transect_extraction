'''
Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options, uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *
#from TE_config_Forsythe2014 import *
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

# TRANSECTS - extendedTrans
# see TE_preprocessing.py
if not arcpy.Exists(extendedTrans):
    trans_presort = 'trans_presort_temp'
    CopyAndWipeFC(trans_orig, trans_presort)
    pythonaddins.MessageBox("Now we'll stop so you can copy existing groups of transects to fill in the gaps. If possible avoid overlapping transects", "Created {}. Proceed with manual processing.".format(trans_presort), 0)
    exit()
# Delete any NAT transects in the new transects layer
if not arcpy.Exists(extendedTrans):
    arcpy.SelectLayerByLocation_management(trans_presort, "ARE_IDENTICAL_TO", trans_orig) # or "SHARE_A_LINE_SEGMENT_WITH"
    if int(arcpy.GetCount_management(trans_presort)[0]) > 0: # if there are old transects in new transects, delete them
        arcpy.DeleteFeatures_management(trans_presort)
    # Append relevant NAT transects to the new transects
    arcpy.SelectLayerByLocation_management(trans_orig, "INTERSECT", barrierBoundary)
    arcpy.Append_management(trans_orig, trans_presort)
    pythonaddins.MessageBox("Now we'll stop so you can check that the transects are ready to be sorted either from the bottom up or top down. ", "Stop for manual processing.".format(trans_presort), 0)
    exit()
if not arcpy.Exists(extendedTrans):
    # Sort
    trans_sort_1 = 'trans_sort_temp'
    trans_sort_ext = 'extTrans_temp'
    trans_sort_1, count1 = SpatialSort(trans_presort,trans_sort_1,"LR",reverse_order=False,sortfield="sort_ID")
    # Extend
    ExtendLine(trans_sort_1,trans_sort_ext,extendlength,proj_code)
    if len(arcpy.ListFields(trans_sort_ext,'OBJECTID*')) == 2:
        ReplaceFields(trans_sort_ext,{'OBJECTID':'OID@'})
    # Make sure transUIDfield counts from 1
    # Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
    arcpy.Sort_management(trans_sort_ext,extendedTrans,transUIDfield)
    with arcpy.da.SearchCursor(extendedTrans, transUIDfield) as cursor:
        row = next(cursor)
    # If transUIDfield does not count from 1, adjust the values
    if row[0] > 1:
        offset = row[0]-1
        with arcpy.da.UpdateCursor(extendedTrans, transUIDfield) as cursor:
            for row in cursor:
                row[0] = row[0]-offset
                cursor.updateRow(row)

# TRANSECTS - extTrans_tidy
if not arcpy.Exists(extTrans_tidy):
    print("Manual work seems necessary to remove transect overlap")
    exit()
    # Select the boundary lines between groups of overlapping transects
    overlapTrans_lines = 'overlapTrans_lines_temp'
    trans_x = 'overlap_points_temp'
    arcpy.CopyFeatures_management(extendedTransects,overlapTrans_lines)
    arcpy.SelectLayerByAttribute_management(extendedTransects, "CLEAR_SELECTION")
    arcpy.Intersect_analysis([extendedTransects,overlapTrans_lines],trans_x,'ALL',output_type="POINT")
    arcpy.SplitLineAtPoint_management(extendedTransects,trans_x,extTrans_tidy)
    arcpy.SelectLayerByLocation_management(extTrans_tidy, "INTERSECT", shoreline, '10 METERS',invert_spatial_relationship='INVERT')
    exit()
if not arcpy.Exists(extTrans_tidy):
    arcpy.DeleteFeatures_management(extTrans_tidy)
    arcpy.CopyFeatures_management(extTrans_tidy, extTrans_tidy_archive)

# ELEVATION
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)

pythonaddins.MessageBox("Pre-processing completed. Continue with transect extraction?", "Continue?", 1)

DeleteTempFiles()

'''_________________PART 1______________________________________________________
Add Feature Positions To Transects, XYZ from DH, DL, & Arm points within 10m of transects
Requires DH, DL, and SHL points, NA transects
'''

print "Starting Part 1"
print "Should take just a few minutes"
startPart1 = time.clock()

inPts_dict = {'ShorelinePts':ShorelinePts, 'dhPts':dhPts, 'dlPts':dlPts}
AddFeaturePositionsToTransects(extendedTrans, extendedTransects, inPts_dict,  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance, home)

DeleteTempFiles()

endPart1 = time.clock()
duration = endPart1 - startPart1
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 1 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________PART 2____________________________________________________
Calculate distances (beach height, beach width, beach slope, max elevation)
Requires: transects with shoreline and dune position information
'''
print "Starting part 2"
print 'Should be quick!'
startPart2 = time.clock()

if not fieldExists(extendedTransects, 'SL_easting'):
    AddFeaturePositionsToTransects(extendedTransects, extendedTransects, {'ShorelinePts':ShorelinePts, 'dhPts':dhPts, 'dlPts':dlPts},  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance, home)
CalculateBeachDistances(extendedTransects, extendedTransects, maxDH, home, dMHW, create_points=True)

# Populate extTrans_tidy with ALL the new fields
newfields = ['DL_z','DH_z','Arm_z',
            'DL_zMHW', 'DH_zMHW','Arm_zMHW',
            "DistDH", "DistDL", "DistArm",
            "SL_easting", "SL_northing",
            "DH_easting", "DH_northing",
            "DL_easting", "DL_northing",
            "Arm_easting", "Arm_northing",
            'MLW_easting','MLW_northing',
          'beach_h_MHW','beachWidth_MHW',
          'beach_h_MLW','beachWidth_MLW',
          'CP_easting','CP_northing','CP_zMHW'] # Ben's label for easting and northing of dune point (DL,DH,or DArm) to be used for beachWidth and beach_h_MHW
arcpy.DeleteField_management(extTrans_tidy, newfields) # in case of reprocessing
arcpy.JoinField_management(extTrans_tidy,transUIDfield,extendedTransects,transUIDfield,newfields)


#####
# Beach width raster
#####



"""
# v1
joinfields = ['beachWidth_MHW']
arcpy.DeleteField_management(extTrans_tidy, joinfields) # in case of reprocessing
arcpy.JoinField_management(extTrans_tidy,transUIDfield,extendedTransects,transUIDfield,joinfields)
trans_buff = 'transbuffer_temp'
arcpy.Buffer_analysis(extTrans_tidy, trans_buff, "25 METERS", line_end_type="FLAT", dissolve_option="LIST", dissolve_field=[transUIDfield, 'beachWidth_MHW'])
arcpy.PolygonToRaster_conversion(trans_buff, 'beachWidth_MHW', beachwidth_rst, cell_assignment='CELL_CENTER', cellsize=5) # cell_center produces gaps only when there is a gap in the features. Max combined area created more gaps.
"""
print("{} have been populated with beach width and used to create {}.".format(extTrans_tidy, beachwidth_rst))

endPart2 = time.clock()
duration = endPart2 - startPart2
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)


'''_________________PART 3______________________________________________________
Dist2Inlet: Calc dist from inlets
# Requires transects and shoreline
'''
print "Starting Part 3"
startPart3 = time.clock()

Dist2Inlet(extendedTransects, shoreline, transUIDfield, xpts='xpts_temp')

joinfields = ['Dist2Inlet']
arcpy.DeleteField_management(extTrans_tidy, joinfields) # in case of reprocessing
arcpy.JoinField_management(extTrans_tidy,transUIDfield,extendedTransects,transUIDfield,joinfields)
print("{} have been populated with distance to inlet.".format(extTrans_tidy))

DeleteTempFiles()

endPart3 = time.clock()
duration = endPart3 - startPart3
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 4 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''___________________PART 4____________________________________________________
Clip transects, get barrier widths
Requires: extended transects, boundary polygon
'''

print "Starting Part 4"
startPart4 = time.clock()

GetBarrierWidths(extendedTransects, trans_clipped, barrierBoundary)

joinfields = ["WidthFull","WidthLand","WidthPart"]

arcpy.DeleteField_management(extTrans_tidy, joinfields) # in case of reprocessing
arcpy.JoinField_management(extTrans_tidy,transUIDfield,trans_clipped,transUIDfield,joinfields)
print("Final population of {} completed. Now creating a raster version as {}. ".format(extTrans_tidy))



#FIXME
extTrans_tidy_fill = extTrans_tidy+'_fill'
arcpy.FeatureClassToFeatureClass_conversion(extTrans_tidy, home, extTrans_tidy_fill)
ReplaceValueInFC(extTrans_tidy_fill,[], None, fill)

JoinFCtoRaster(rst_transPopulated, extTrans_tidy, rst_transID, transUIDfield='sort_ID')

def JoinFCtoRaster(out_rst, in_fc, in_rst, use_fill_values=True, transUIDfield='sort_ID'):
    if not arcpy.Exists(in_rst):
        in_rst = TransectsToContinuousRaster(extTrans_tidy, in_rst, cellsize_rst, transUIDfield)
    arcpy.MakeTableView_management(in_fc, 'tableview')
    # if use_fill_values:
    #     ReplaceValueInFC('tableview',[], None, fill)
    arcpy.MakeRasterLayer_management(in_rst, 'rst_lyr')
    arcpy.AddJoin_management('rst_lyr', 'Value', 'tableview', transUIDfield)
    arcpy.CopyRaster_management('rst_lyr', out_rst)
    return out_rst
"""
# Get raster of transect IDs
if not arcpy.Exists(rst_transID):
    rst_transID = TransectsToContinuousRaster(extTrans_tidy, rst_transID, cellsize_rst, transUIDfield)
arcpy.MakeTableView_management(extTrans_tidy, 'trans_tableview')
arcpy.MakeRasterLayer_management(rst_transID, 'rst_trans_lyr')
arcpy.AddJoin_management('rst_trans_lyr', 'Value', 'trans_tableview', transUIDfield)
arcpy.env.outputCoordinateSystem = utmSR
arcpy.env.scratchWorkspace = home
arcpy.CopyRaster_management('rst_trans_lyr', rst_transPopulated)
"""



# Save final transects before moving on to segmenting them
arcpy.FeatureClassToFeatureClass_conversion(extTrans_tidy,home,transects_final)
print("Creation of " + transects_final + " completed. ")

# Remove temp files
DeleteTempFiles()

endPart4 = time.clock()
duration = endPart4 - startPart4
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "Part 2 completed in %dh:%dm:%fs" % (hours, minutes, seconds)




'''______________________PART 5_________________________________________________
Create Transect Segment points and sample data
Requires: clipped transects with shoreline fields
'''

print 'Starting Part 5'
print 'Expect a 3 to 15 minute wait'
startPart5 = time.clock()

#FIXME: may not be necessary to join before converting to points...
if not fieldExists(extTrans_tidy,'DistDH'):
    if not fieldExists(extendedTransects, 'SL_easting'):
        AddFeaturePositionsToTransects(extendedTransects, extendedTransects, {'ShorelinePts':ShorelinePts, 'dhPts':dhPts, 'dlPts':dlPts},  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance, home)
    if not fieldExists(extendedTransects, 'beachWidth_MHW'):
        CalculateBeachDistances(extendedTransects, extendedTransects, maxDH, home, dMHW, create_points=True)
    joinfields = ['SL_easting', 'SL_northing','DistDH', 'DistDL', 'DistArm']
    arcpy.DeleteField_management(extTrans_tidy, joinfields) # in case of reprocessing
    arcpy.JoinField_management(extTrans_tidy,transUIDfield,extendedTransects,transUIDfield,joinfields)
if not fieldExists(extTrans_tidy, 'WidthPart'):
    if not fieldExists(extTrans_tidy, "WidthPart"):
        GetBarrierWidths(extendedTransects, trans_clipped, barrierBoundary)
    joinfields = ["WidthFull","WidthLand","WidthPart"]
    # Save final transects before moving on to segmenting them
    arcpy.DeleteField_management(extTrans_tidy, joinfields) # in case of reprocessing
    arcpy.JoinField_management(extTrans_tidy,transUIDfield,extendedTransects,transUIDfield,joinfields)

# Split transects into points
transPts_presort = SplitTransectsToPoints(extTrans_tidy, 'transPts_presort', barrierBoundary, home, clippedtrans='trans_clipped2island')

# Calculate distance of point from shoreline and dunes (Dist_Seg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
# Requires fields: SL_easting, SL_northing, WidthPart, seg_x, seg_y
#FIXME Could be replaced by raster processing...

ReplaceFields(transPts_presort,{'seg_x':'SHAPE@X','seg_y':'SHAPE@Y'}) # Add xy for each segment center point

# extTrans_tidy must have SL_easting, SL_northing, and WidthPart
distfields = ['Dist_Seg', 'Dist_MHWbay', 'seg_x', 'seg_y', 'SL_easting', 'SL_northing', 'WidthPart', 'DistSegDH', 'DistSegDL','Dist_Seg','DistDH', 'DistDL', 'DistArm', 'DistSegArm']
AddNewFields(transPts_presort, distfields)
with arcpy.da.UpdateCursor(transPts_presort, distfields) as cursor:
    for row in cursor:
        flist = cursor.fields
        try:
            seg_x = row[flist.index('seg_x')]
            SL_easting = row[flist.index('SL_easting')]
            seg_y = row[flist.index('seg_y')]
            SL_northing = row[flist.index('SL_northing')]
            row[flist.index('Dist_Seg')] = dist2mhw = math.sqrt((seg_x - SL_easting)**2 + (seg_y - SL_northing)**2) # hypot(row[4]-row[2],row[5]-row[3])
            row[flist.index('Dist_MHWbay')] = row[flist.index('WidthPart')] - dist2mhw
            try:
                row[flist.index('DistSegDH')] = dist2mhw-row[flist.index('DistDH')]
            except TypeError:
                pass
            try:
                row[flist.index('DistSegDL')] = dist2mhw-row[flist.index('DistDL')]
            except TypeError:
                pass
            try:
                row[flist.index('DistSegArm')] = dist2mhw-row[flist.index('DistArm')]
            except TypeError:
                pass
        except TypeError:
            pass
        cursor.updateRow(row)

# Sort on transUIDfield and DistSeg (id_temp)
if open_mxd: #FIXME
    RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, tranSplitPts, [[transUIDfield,'ASCENDING'],['Dist_Seg','ASCENDING']])
ReplaceFields(tranSplitPts,{'SplitSort':'OID@'})

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

#Get elevation and slope at points ### TAKES A WHILE
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
