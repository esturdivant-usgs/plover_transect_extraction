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
from TE_config_Forsythe2014 import *

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
    trans_sort_1, count1 = SpatialSort(trans_presort,trans_sort_1,"LR",reverse_order=False,sortfield="sort_ID")
    # Extend
    ExtendLine(trans_sort_1,extendedTrans,extendlength,proj_code)
    if len(arcpy.ListFields(extendedTrans,'OBJECTID*')) == 2:
        ReplaceFields(extendedTrans,{'OBJECTID':'OID@'})

# Work with duplicate of original transects to preserve them - version for modification has the year added to the transect filename
arcpy.Sort_management(extendedTrans,extendedTransects,transUIDfield)
# Make sure transUIDfield counts from 1
with arcpy.da.SearchCursor(extendedTransects, transUIDfield) as cursor:
    row = next(cursor)
# If transUIDfield does not count from 1, adjust the values
if row[0] > 1:
    offset = row[0]-1
    with arcpy.da.UpdateCursor(extendedTransects, transUIDfield) as cursor:
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
Create Extended transects, DH & DL points within 10m of transects
Requires DH, DL, and SHL points, NA transects
'''

print "Starting Part 1"
print "Should take just a few minutes"
startPart1 = time.clock()

inPts_dict = {'ShorelinePts':ShorelinePts, 'dhPts':dhPts, 'dlPts':dlPts}
AddFeaturePositionsToTransects(extendedTransects, inPts_dict,  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance)

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
    AddFeaturePositionsToTransects(extendedTransects, {'ShorelinePts':ShorelinePts, 'dhPts':dhPts, 'dlPts':dlPts},  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance)
CalculateBeachDistances(extendedTransects, maxDH, create_points=True)
def CalculateBeachDistances(extendedTransects, maxDH, create_points=True):
    # Set fields that will be used to calculate beach width and store the results
    fieldlist = ['DL_z','DH_z','Arm_z',
                'DL_zMHW', 'DH_zMHW','Arm_zMHW',
                "DistDH", "DistDL", "DistArm",
                "SL_easting", "SL_northing",
                "DH_easting", "DH_northing",
                "DL_easting", "DL_northing",
                "Arm_easting", "Arm_northing"]
    beachWidth_fields = ['MLW_easting',
              'MLW_northing',
              'beach_h_MHW',
              'beachWidth_MHW',
              'beach_h_MLW',
              'beachWidth_MLW',
              'CP_easting','CP_northing', # Ben's label for easting and northing of dune point (DL,DH,or DArm) to be used for beachWidth and beach_h_MHW
              'CP_zMHW']
    distfields = ['DistDH','DistDL','DistArm'] # distance from shoreline
    # Add fields if they don't already exist
    AddNewFields(extendedTransects,fieldlist)
    #AddNewFields(baseName,'Source_beachwidth','TEXT')
    AddNewFields(extendedTransects, beachWidth_fields)
    # Calculate
    errorct = transectct = 0
    with arcpy.da.UpdateCursor(extendedTransects,'*') as cursor:
        for row in cursor:
            flist = cursor.fields
            transectct +=1
            try:
                row[flist.index('DL_zMHW')] = row[flist.index('DL_z')] + dMHW
            except TypeError:
                pass
            try:
                row[flist.index('DH_zMHW')] = row[flist.index('DH_z')] + dMHW
            except TypeError:
                pass
            try:
                row[flist.index('Arm_zMHW')] = row[flist.index('Arm_z')] + dMHW
            except TypeError:
                pass
            # Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
            sl_x = row[flist.index('SL_easting')]
            sl_y = row[flist.index('SL_northing')]
            try:
                row[flist.index('DistDH')] = hypot(sl_x - row[flist.index('DH_easting')], sl_y - row[flist.index('DH_northing')])
            except TypeError:
                pass
            try:
                row[flist.index('DistDL')] = hypot(sl_x - row[flist.index('DL_easting')], sl_y - row[flist.index('DL_northing')])
            except TypeError:
                pass
            try:
                row[flist.index('DistArm')] = hypot(sl_x - row[flist.index('Arm_easting')], sl_y - row[flist.index('Arm_northing')])
            except TypeError:
                pass
            # Find which of DL, DH, and Arm is closest to MHW and not Null (exclude DH if higher than maxDH)
            cp = FindNearestPointWithZvalue(row,flist,distfields,maxDH) # prefix of closest point metric
            if cp: # if closest point was found calculate beach width with that point, otherwise skip
                # Calculate beach width = Euclidean distance from dune (DL, DH, or Arm) to MHW and MLW
                # Set values from each row
                d_x = row[flist.index(cp+'_easting')]
                d_y = row[flist.index(cp+'_northing')]
                b_slope = row[flist.index('Bslope')]
                sl_x = row[flist.index('SL_easting')]
                sl_y = row[flist.index('SL_northing')]
                #beachWidth_MHW = CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y)
                mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_MLW(oMLW,d_x,d_y,b_slope,sl_x,sl_y)
                beach_h_MHW = row[flist.index(cp+'_zMHW')]
                # update Row values
                row[flist.index('MLW_easting')] = mlw_x
                row[flist.index('MLW_northing')] = mlw_y
                row[flist.index('beach_h_MHW')] = beach_h_MHW
                row[flist.index('beachWidth_MHW')] = row[flist.index('Dist'+cp)]
                row[flist.index('beach_h_MLW')] = beach_h_MHW-oMLW
                row[flist.index('beachWidth_MLW')] = beachWidth_MLW
                #row[flist.index('Source_beachwidth')] = cp
                row[flist.index('CP_easting')] = row[flist.index(cp+'_easting')]
                row[flist.index('CP_northing')] = row[flist.index(cp+'_northing')]
                row[flist.index('CP_zMHW')] = row[flist.index(cp+'_zMHW')]
            else:
                errorct +=1
                pass
            cursor.updateRow(row)
    # Report
    print("Beach Width could not be calculated for {} out of {} transects.".format(errorct,transectct))
    # Create MLW and CP points for error checking
    if create_points:
        arcpy.MakeXYEventLayer_management(extendedTransects,'MLW_easting','MLW_northing',MLWpts+'_lyr',utmSR)
        arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)
        arcpy.MakeXYEventLayer_management(extendedTransects,'CP_easting','CP_northing',CPpts+'_lyr',utmSR)
        arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)
    # Return
    return extendedTransects

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


'''______________________PART 5_________________________________________________
Create Transect Segment points and sample data
Requires: clipped transects with shoreline fields
'''

print 'Starting Part 5'
print 'Expect a 3 to 15 minute wait'
startPart5 = time.clock()

"""
# Split transects into segments
"""
# Convert transects to 5m points: multi to single; split lines; segments to center points
#arcpy.MultipartToSinglepart_management(baseName, tranSplitPts+'Sing_temp')
input1 = os.path.join(home,'singlepart_temp')
output = os.path.join(home, 'singlepart_split_temp')
arcpy.MultipartToSinglepart_management(baseName, input1)
arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx")
arcpy.XToolsGP_SplitPolylines_xtp(input1,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
transPts_presort = 'segDistances_presort'
arcpy.FeatureToPoint_management('singlepart_split_temp',transPts_presort)

"""
# Calculate distance of point from shoreline and dunes (Dist_Seg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
# Requires fields: SL_easting, SL_northing, WidthPart, seg_x, seg_y
Could be replaced by raster processing... #FIXME
"""
ReplaceFields(transPts_presort,{'seg_x':'SHAPE@X','seg_y':'SHAPE@Y'}) # Add xy for each segment center point
distfields = ['Dist_Seg', 'Dist_MHWbay', 'seg_x', 'seg_y', 'SL_easting', 'SL_northing', 'WidthPart', 'DistSegDH', 'DistSegDL','Dist_Seg','DistDH', 'DistDL', 'DistArm', 'DistSegArm']
AddNewFields(tranSplitPts, distfields)
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
        except:
            pass
        try:
            row[flist.index('DistSegDH')] = dist2mhw-row[flist.index('DistDH')]
        except:
            pass
        try:
            row[flist.index('DistSegDL')] = dist2mhw-row[flist.index('DistDL')]
        except:
            pass
        try:
            row[flist.index('DistSegArm')] = dist2mhw-row[flist.index('DistArm')]
        except:
            pass
        cursor.updateRow(row)


# Sort on transUIDfield and DistSeg (id_temp)
RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, tranSplitPts, [[transUIDfield,'ASCENDING'],['Dist_Seg','ASCENDING']])
ReplaceFields(tranSplitPts,{'SplitSort':'OID@'})

"""
ReplaceFields(transPts_presort,{'seg_x':'SHAPE@X','seg_y':'SHAPE@Y'}) # Add xy for each segment center point
AddNewFields(transPts_presort, ["Dist_Seg","Dist_MHWbay"])
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
"""
# Tidy up
arcpy.DeleteField_management(tranSplitPts,["StartX","StartY","ORIG_FID"])
DeleteTempFiles()

"""
Save feature class and shapefile with just beach width and sort_ID fields
"""
fmap = """sort_ID "sort_ID" true true false 2 Short 0 0 ,First,#,{site}{year}_transPts_working,sort_ID,-1,-1;beachWidth_MHW "beachWidth_MHW" true true false 8 Double 0 0 ,First,#,{site}{year}_transPts_working,beachWidth_MHW,-1,-1""".format(**SiteYear_strings)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts,home,tranSplitPts_bw,field_mapping=fmap)
#DeleteExtraFields(tranSplitPts_bw,['sort_ID','SplitSort','beachWidth_MHW'])
ReplaceValueInFC(tranSplitPts_bw,[], None, fill)
arcpy.FeatureClassToFeatureClass_conversion(tranSplitPts_bw,out_dir,tranSplitPts_bw+'.shp')

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
