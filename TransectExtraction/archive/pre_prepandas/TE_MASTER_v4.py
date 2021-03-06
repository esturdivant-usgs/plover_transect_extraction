
'''
Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options,
        uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
import arcpy
import time
import pythonaddins
import sys
# path to TransectExtraction module
sys.path.append(r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction")
from TransectExtraction import *
from TE_config_Forsythe2010 import *


start = time.clock()

"""
Pre-processing
"""
# Check presence of default files in gdb
e_trans = SetInputFCname(home, 'extendedTrans', extendedTrans, system_ext=False)
t_trans = SetInputFCname(home, 'extTrans_tidy', extTrans_tidy, False)
i_name = SetInputFCname(home, 'inlets delineated (inletLines)', inletLines, False)
dhPts = SetInputFCname(home, 'dune crest points (dhPts)', dhPts)
dlPts = SetInputFCname(home, 'dune toe points (dlPts)', dlPts)
ShorelinePts = SetInputFCname(home, 'shoreline points (ShorelinePts)', ShorelinePts)
armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)
bb_name = SetInputFCname(home, 'barrier island polygon (barrierBoundary)',
                         barrierBoundary, False)
new_shore = SetInputFCname(home, 'shoreline between inlets', shoreline, False)
elevGrid_5m = SetInputFCname(home, 'DEM raster at 5m res (elevGrid_5m)',
                             elevGrid_5m, False)

# DUNE POINTS
# Replace fill values with Null
ReplaceValueInFC(dhPts, oldvalue=fill, newvalue=None, fields=["dhigh_z"])
ReplaceValueInFC(dlPts, oldvalue=fill, newvalue=None, fields=["dlow_z"])
ReplaceValueInFC(ShorelinePts, oldvalue=fill, newvalue=None, fields=["slope"])
# Populate ID with OID?

# INLETS
if not i_name:
    arcpy.CreateFeatureclass_management(home, inletLines, 'POLYLINE',
        spatial_reference=arcpy.SpatialReference(proj_code))
    print("{} created. Now we'll stop for you to manually create lines at each inlet.")
    exit()
else:
    inletLines = i_name

# BOUNDARY POLYGON
if not bb_name:
    rawbarrierline = DEMtoFullShorelinePoly(elevGrid,
        '{site}{year}'.format(**SYvars), MTL, MHW, inletLines, ShorelinePts)
    # Eliminate any remnant polygons on oceanside
    if pythonaddins.MessageBox('Ready to delete selected features from {}?'.format(rawbarrierline), '', 4) == 'Yes':
        arcpy.DeleteFeatures_management(rawbarrierline)
    else:
        print("Ok, redo.")
        exit()

    barrierBoundary = NewBNDpoly(rawbarrierline, ShorelinePts, barrierBoundary,
                                 '25 METERS', '50 METERS')
else:
    barrierBoundary = bb_name

# SHORELINE
if not new_shore:
    shoreline = CreateShoreBetweenInlets(barrierBoundary, inletLines,
                                         shoreline, ShorelinePts, proj_code)
else:
    shoreline = new_shore

# TRANSECTS - extendedTrans
# Copy transects from archive directory
if not e_trans:
    print("Use TE_preprocess_transects.py to create the transects for processing.")
    exit()

# ELEVATION
if not arcpy.Exists(elevGrid_5m):
    ProcessDEM(elevGrid, elevGrid_5m, utmSR)

pythonaddins.MessageBox("Pre-processing completed. Continue with transect extraction?", "Continue?", 1)

DeleteTempFiles()

'''_________________PART 1_____________________________________________________
Add XYZ from DH, DL, & Arm points within 10m of transects
Requires DH, DL, and SHL points, NA transects
*SPATIAL*
--> extendedTransects (p0)
--> dhPts, dlPts, ShorelinePts, shoreline, armoreLines,
--> elevGrid
'''
inPtsDict={'ShorelinePts': ShorelinePts, 'dhPts': dhPts, 'dlPts': dlPts,
'shoreline': shoreline, 'armorLines': armorLines}
# ShorelinePtsToTransects(extendedTransects, inPtsDict, transUIDfield, proj_code, pt2trans_disttolerance)
AddFeaturePositionsToTransects(in_trans=orig_extTrans, out_fc=extendedTransects,
    inPtsDict=inPtsDict, IDfield=transUIDfield,
    proj_code=proj_code, disttolerance=pt2trans_disttolerance, home=home,
    elevGrid_5m=elevGrid_5m)

# May need to add process that takes

'''___________________PART 2____________________________________________________
Calculate distances (beach height, beach width, beach slope, max elevation)
Requires: transects with shoreline and dune position information
*NON-SPATIAL*
--> extendedTransects w/ position fields (p1)
'''
arcpy.env.workspace = home
DeleteTempFiles()
print("Starting part 2 - Calculate beach geometry - Should be quick!")
CalculateBeachDistances(extendedTransects, extendedTransects, maxDH, home, dMHW, oMLW,
                        MLWpts, CPpts, create_points=True, skip_field_check=False)
# print "Converting the transects to a raster: {}".format(rst_transPopulated)
# extT_fill, rst_transPop = FCtoRaster(extendedTransects, rst_transID,  # orig_tidytrans or rst_transID
#                                      rst_transPopulated, transUIDfield,
#                                      home, fill=fill)
# print "Saving the raster outside of the geodatabase: {}".format(os.path.join(out_dir, rst_trans_grid))
# arcpy.CopyRaster_management(rst_transPop, os.path.join(out_dir, rst_trans_grid))

'''_________________PART 3_____________________________________________________
Dist2Inlet: Calc dist from inlets
# Requires transects and shoreline
*SPATIAL*
--> extendedTransects
--> shoreline w/ SUM_Join_Count field
'''
arcpy.env.workspace = home
DeleteTempFiles()
#RemoveLayerFromMXD('*_temp')
print "Starting Part 3 - Distance to Inlet"
Dist2Inlet(extendedTransects, shoreline, transUIDfield, xpts='shoreline2trans')


'''___________________PART 4___________________________________________________
Clip transects, get barrier widths
Requires: extended transects, boundary polygon
*SPATIAL*
--> extendedTransects
--> barrierBoundary
'''
DeleteTempFiles()
print "Starting Part 4 - Get barrier widths and output transects"
GetBarrierWidths(extendedTransects, barrierBoundary, shoreline, IDfield=transUIDfield, out_clipped_trans='trans_clipped2island')

'''___________________OUTPUT TRANSECTS_________________________________________
Output populated transects as: extendedTransects, extTrans_tidy, rst_transPopulated
Requires: extended transects, extTrans_tidy
--> extended
'''
# OUTPUT: raster version of populated transects (with fill values)
print "Converting the transects to a raster: {}".format(rst_transPopulated)
extT_fill, rst_transPop = FCtoRaster(extendedTransects, rst_transID,
                                     rst_transPopulated, transUIDfield,
                                     home, fill=fill)
print "Saving the raster outside of the geodatabase: {}".format(out_dir)
arcpy.CopyRaster_management(rst_transPop, os.path.join(out_dir, rst_trans_grid))

# Remove temp files
DeleteTempFiles()

'''______________________PART 5________________________________________________
Create Transect Segment points and sample data
Requires: extTrans_tidy with shoreline and distance fields, barrierBoundary
'''
DeleteTempFiles()
print 'Starting Part 5'
print 'Expect a 3 to 15 minute wait'
startPart5 = time.clock()

# transdistfields = ['DistDH', 'DistDL', 'DistArm', 'SL_x', 'SL_y', 'WidthPart']
# missing_fields = fieldsAbsent(extTrans_tidy, transdistfields)
# if missing_fields:
#     arcpy.JoinField_management(extTrans_tidy, transUIDfield, extendedTransects,
#                                transUIDfield, missing_fields)
# Split transects into points
SplitTransectsToPoints(extTrans_tidy, transPts_presort, barrierBoundary,
                       home, clippedtrans='trans_clipped2island')
# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
CalculatePointDistances(transPts_presort, extendedTransects)
# Sort on transUIDfield and DistSeg (id_temp)
RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, transPts, [[transUIDfield,
                      'ASCENDING'], ['Dist_Seg', 'ASCENDING']])
ReplaceFields(transPts, {'SplitSort': 'OID@'})

# Tidy up
arcpy.DeleteField_management(transPts, ["StartX", "StartY", "ORIG_FID"])
DeleteTempFiles()

# Report time
# endPart5 = time.clock()
# duration = endPart5 - startPart5
# hours, remainder = divmod(duration, 3600)
# minutes, seconds = divmod(remainder, 60)
# print "Part 5 completed in %dh:%dm:%fs" % (hours, minutes, seconds)

'''____________________________________________________________________________

   /\\\\\\\\\\\\\                   /\\\\\
   \/\\\/////////\\\               /\\\\/
    \/\\\       \/\\\             /\\\//
     \/\\\\\\\\\\\\\/            /\\\\\\\\\\\
      \/\\\/////////             /\\\\///////\\\
       \/\\\                     \/\\\      \//\\\
        \/\\\                     \//\\\      /\\\
         \/\\\                      \///\\\\\\\\\/
          \///                       \/////////
_______________________________________________________________________________
Extract elev and slope at points and calculate average elevation per transect
Requires: tranSplitPts (points at which to extract elevation), elevGrid
'''
print "Starting Part 6"
print "Expect ~ minutes to extract values from points"

# Create slope grid if doesn't already exist
if not arcpy.Exists(slopeGrid):
    arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')

# Get elevation and slope at points ### TAKES A WHILE
if arcpy.Exists(pts_elevslope):
    # Join elevation and slope values from a previous iteration of the script
    arcpy.JoinField_management(transPts, "SplitSort", pts_elevslope,
                               "SplitSort", ['ptZ', 'ptZmhw', 'ptSlp'])
else:
    arcpy.DeleteField_management(transPts, ['ptZ', 'ptSlp'])  # if reprocessing
    arcpy.sa.ExtractMultiValuesToPoints(transPts, [[elevGrid_5m, 'ptZ'],
                                        [slopeGrid, 'ptSlp']])
    AddNewFields(transPts, 'ptZmhw')
    with arcpy.da.UpdateCursor(transPts, ['ptZ', 'ptZmhw']) as cursor:
        for row in cursor:
            try:
                row[1] = row[0] - MHW
            except:
                pass
            cursor.updateRow(row)
    # Save pts with elevation and slope to archived file
    fmaps = 'SplitSort "SplitSort" true true false 8 Double 0 0 , First, #, {source}, SplitSort,-1,-1;'\
            'ptZ "ptZ" true true false 4 Float 0 0 ,First,#, {source}, ptZ,-1,-1;'\
            'ptSlp "ptSlp" true true false 4 Float 0 0 ,First,#, {source}, ptSlp,-1,-1;'\
            'ptZmhw "ptZmhw" true true false 8 Double 0 0 ,First,#, {source}, ptZmhw,-1,-1;'\
            'sort_ID "sort_ID" true true false 2 Short 0 0 ,First,#, {source},'\
            ' sort_ID,-1,-1'.format(**{'source': transPts})
    # fieldlist = ['SplitSort', 'ptZ', 'ptSlp', 'ptZmhw']
    # fmaps = arcpy.FieldMappings()
    # for f in fieldlist:
    #     fm = arcpy.FieldMap()
    #     fm.addInputField(transPts, f)
    #     fmaps.addFieldMap(fm)
    arcpy.FeatureClassToFeatureClass_conversion(transPts, home, pts_elevslope,
                                                 field_mapping=fmaps)

"""
# Get max_Z and mean_Z for each transect
"""
# save max and mean in out_stats table using Statistics_analysis
arcpy.Statistics_analysis(transPts, out_stats, [['ptZmhw', 'MAX'], ['ptZmhw',
                          'MEAN'], ['ptZmhw', 'COUNT']], transUIDfield)
# remove mean values if fewer than 80% of 5m points had elevation values
with arcpy.da.UpdateCursor(out_stats, ['*']) as cursor:
    for row in cursor:
        count = row[cursor.fields.index('COUNT_ptZmhw')]
        if count is None:
            row[cursor.fields.index('MEAN_ptZmhw')] = None
            cursor.updateRow(row)
        elif count / row[cursor.fields.index('FREQUENCY')] <= 0.8:
            row[cursor.fields.index('MEAN_ptZmhw')] = None
            cursor.updateRow(row)

# add mean and max fields to points FC using JoinField_management
# very slow: over 1 hr (Forsythe: 1:53)
arcpy.JoinField_management(transPts, transUIDfield, out_stats, transUIDfield,
                           ['MAX_ptZmhw', 'MEAN_ptZmhw'])
try:
    arcpy.DeleteField_management(extendedTransects, ['MAX_ptZmhw', 'MEAN_ptZmhw'])
    arcpy.JoinField_management(extendedTransects, transUIDfield, out_stats,
                           transUIDfield, ['MAX_ptZmhw', 'MEAN_ptZmhw'])
except:
    arcpy.JoinField_management(extendedTransects, transUIDfield, transPts,
                           transUIDfield, ['MAX_ptZmhw', 'MEAN_ptZmhw'])

'''______________________PART 7________________________________________________
Save final files: extendedTransects -> extendedTransects_null,
extT_fill
'''

missing_Tfields = fieldsAbsent(extendedTransects, transect_fields)
if missing_Tfields:
    print("Fields '{}' not present in transects file '{}'.".format(
          missing_Tfields, extendedTransects))
# Save final transects with fill values
extT_fill, out_rst = FCtoRaster(in_fc=extendedTransects, in_ID=rst_transID,
                                out_rst=rst_trans_grid, IDfield=transUIDfield,
                                home=home, fill=fill, cell_size=cellsize_rst)
#arcpy.CopyRaster_management(out_rst, os.path.join(out_dir, rst_trans_grid))

# Check that transPts have all fields from extendedTransects and
# join those that are missing.
missing_fields = ['SL_Lat', 'SL_Lon', 'SL_x', 'SL_y', 'Bslope']
missing_fields = fieldsAbsent(transPts, transect_fields)
if missing_fields:
    print("Fields '{}' not present in 5m points file '{}'.".format(
          missing_fields, transPts))
# Save final transect points before moving on to segmenting them
arcpy.DeleteField_management(transPts, missing_fields)  # in case reprocessing
arcpy.JoinField_management(transPts, transUIDfield, extendedTransects,
                           transUIDfield, missing_fields)

# Save pts as feature class with Nulls (transSplitPts_final)
arcpy.FeatureClassToFeatureClass_conversion(transPts, home, transPts_null)
# Replace Null values with fills and save as FC, SHP, and CSV
arcpy.FeatureClassToFeatureClass_conversion(transPts, home, transPts_fill)
ReplaceValueInFC(transPts_fill, None, fill)
arcpy.FeatureClassToFeatureClass_conversion(transPts_fill, out_dir,
                                            transPts_shp+'.shp')
arcpy.TableToTable_conversion(transPts_fill, out_dir,
                              transPts_fill+'.csv')

finalmessage = "The final products ({}) were exported as a shapefile and CSV "\
               "to {}. \n\nNow enter the USER to save the table: \n\n"\
               "1. Open the CSV in Excel and then Save as... a .xlsx file. \n"\
               "2. Open the XLS file in Matlab with the data checking script "\
               "to check for errors! ".format(transPts_shp, out_dir)
print(finalmessage)
pythonaddins.MessageBox(finalmessage, 'Final Steps')

arcpy.FeatureClassToFeatureClass_conversion(transPts, home, transPts_fill)
ReplaceValueInFC(transPts_fill, None, fill)
arcpy.TableToTable_conversion(transPts_fill, out_dir,
                              transPts_fill+'.csv')
extTrans_fill = '{site}{year}_extTrans_fill'.format(**SiteYear_strings)
arcpy.FeatureClassToFeatureClass_conversion(extendedTransects, home, extTrans_fill)
ReplaceValueInFC(extTrans_fill, None, fill)
arcpy.TableToTable_conversion(extTrans_fill, out_dir,
                            extTrans_fill+'.csv')

end = time.clock()
duration = end - start
hours, remainder = divmod(duration, 3600)
minutes, seconds = divmod(remainder, 60)
print "\nProcessing completed in %dh:%dm:%fs" % (hours, minutes, seconds)
