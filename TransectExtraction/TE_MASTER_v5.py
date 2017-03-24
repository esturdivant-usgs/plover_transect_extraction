
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
import pandas as pd
import numpy as np
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
# ShorelinePtsToTransects(extendedTransects, inPtsDict, tID_fld, proj_code, pt2trans_disttolerance)
AddFeaturePositionsToTransects(in_trans=orig_extTrans, out_fc=extendedTransects,
    inPtsDict=inPtsDict, IDfield=tID_fld,
    proj_code=proj_code, disttolerance=pt2trans_disttolerance, home=home,
    elevGrid_5m=elevGrid_5m)


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
Dist2Inlet(extendedTransects, shoreline, tID_fld, xpts='shoreline2trans')


'''___________________PART 4___________________________________________________
Clip transects, get barrier widths
Requires: extended transects, boundary polygon
*SPATIAL*
--> extendedTransects
--> barrierBoundary
'''
DeleteTempFiles()
print "Starting Part 4 - Get barrier widths and output transects"
GetBarrierWidths(extendedTransects, barrierBoundary, shoreline, IDfield=tID_fld, out_clipped_trans='trans_clipped2island')

'''___________________OUTPUT TRANSECTS_________________________________________
Output populated transects as: extendedTransects, extTrans_tidy, rst_transPopulated
Requires: extended transects, extTrans_tidy
*SPATIAL*
'''
# OUTPUT: raster version of populated transects (with fill values)
print "Converting the transects to a raster: {}".format(rst_transPopulated)
extT_fill, rst_transPop = FCtoRaster(extendedTransects, rst_transID,
                                     rst_transPopulated, tID_fld,
                                     home, fill=fill)
print "Saving the raster outside of the geodatabase: {}".format(out_dir)
arcpy.CopyRaster_management(rst_transPop, os.path.join(out_dir, rst_trans_grid))

trans_df = FCtoDF(extendedTransects, id_fld=tID_fld)

# Remove temp files
DeleteTempFiles()

'''______________________PART 5________________________________________________
Create Transect Segment points and sample data
Requires: extTrans_tidy with shoreline and distance fields, barrierBoundary
*SPATIAL*
'''
DeleteTempFiles()
print 'Starting Part 5 \nExpect a 3 to 15 minute wait'
startPart5 = time.clock()

# transdistfields = ['DistDH', 'DistDL', 'DistArm', 'SL_x', 'SL_y', 'WidthPart']
# missing_fields = fieldsAbsent(extTrans_tidy, transdistfields)
# if missing_fields:
#     arcpy.JoinField_management(extTrans_tidy, tID_fld, extendedTransects,
#                                tID_fld, missing_fields)
# Split transects into points
SplitTransectsToPoints(extTrans_tidy, transPts_presort, barrierBoundary,
                       home, clippedtrans='trans_clipped2island')
# Calculate DistSeg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
CalculatePointDistances(transPts_presort, extendedTransects)
# Sort on tID_fld and DistSeg (id_temp)
RemoveLayerFromMXD(transPts_presort)
arcpy.Sort_management(transPts_presort, transPts, [[tID_fld,
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

'''______________________PART 6________________________________________________
Extract elev and slope at points and calculate average elevation per transect
Requires: tranSplitPts (points at which to extract elevation), elevGrid
*SPATIAL*
'''
print "Starting Part 6"

if not overwrite_Z:
    overwrite_Z = os.path.exists(os.path.join(working_dir, pts_elevslope+'.pkl'))

# Get elevation and slope at points
if not overwrite_Z:
    # Create slope grid if doesn't already exist
    if not arcpy.Exists(slopeGrid):
        arcpy.Slope_3d(elevGrid_5m, slopeGrid, 'PERCENT_RISE')
    # Extract elevation and slope at points
    arcpy.DeleteField_management(transPts, ['ptZ', 'ptSlp', 'ptZmhw'])  # if reprocessing
    arcpy.sa.ExtractMultiValuesToPoints(transPts, [[elevGrid_5m, 'ptZ'],
                                        [slopeGrid, 'ptSlp']])
    # convert points to dataframe
    pts_df = FCtoDF(transPts, id_fld=pts_id)
    pts_df = pts_df.join(pts_df['ptZ'].subtract(MHW), rsuffix='mhw')
    # Save pts with elevation and slope to archived file
    pts_df.to_pickle(os.path.join(working_dir, pts_elevslope + '.pkl'))
else:
    # Join elevation and slope values from a previous iteration of the script
    zpts_df = pd.read_pickle(os.path.join(working_dir, pts_elevslope + '.pkl'))
    pts_df = FCtoDF(transPts, id_fld=pts_id)
    pts_df = pts_df.join(zpts_df)

# Remove extra columns
pts_df.drop(extra_fields, axis=1, inplace=True, errors='ignore')

'''______________________PART 6b________________________________________________
Get max_Z and mean_Z for each transect
Requires: transPts
'''
# Aggregate ptZmhw to max and mean and join to transPts and extendedTransects
# transPts = SummarizePointElevation(transPts, extendedTransects, out_stats, tID_fld)

zmhw = pts_df.groupby(tID_fld)['ptZmhw'].agg([np.mean, np.max])
zmhw.rename(columns={'mean':'mean_Zmhw', 'amax':'max_Zmhw'}, inplace=True)
trans_df = trans_df.join(zmhw,  how='outer')

'''______________________PART 7a________________________________________________
Save final files: extendedTransects -> extendedTransects_null,
extT_fill
'''
trans_df = trans_df.drop(tID_fld, axis=1)
dup_cols = pts_df.axes[1].intersection(trans_df.axes[1])
pts_df = pts_df.drop(dup_cols, axis=1)
pts_final = pts_df.join(trans_df, on=tID_fld, how='outer')
# pts_final = join_with_dataframes(extendedTransects, transPts, tID_fld, 'SplitSort')
pts_final.to_csv(os.path.join(out_dir, transPts_fill +'.csv'))

finalmessage = "The final products ({}) were exported as a shapefile and CSV "\
               "to {}. \n\nNow enter the USER to save the table: \n\n"\
               "1. Open the CSV in Excel and then Save as... a .xlsx file. \n"\
               "2. Open the XLS file in Matlab with the data checking script "\
               "to check for errors! ".format(transPts_shp, out_dir)
print(finalmessage)
pythonaddins.MessageBox(finalmessage, 'Final Steps')

'''______________________PART 7b________________________________________________
Save final files: extendedTransects -> extendedTransects_null,
extT_fill
'''
missing_Tfields = fieldsAbsent(extendedTransects, transect_fields)

# Save final transects with fill values
extT_fill, out_rst = FCtoRaster(in_fc=extendedTransects, in_ID=rst_transID,
                                out_rst=rst_trans_grid, IDfield=tID_fld,
                                home=home, fill=fill, cell_size=cellsize_rst)
#arcpy.CopyRaster_management(out_rst, os.path.join(out_dir, rst_trans_grid))

# Check that transPts have all fields from extendedTransects and
# join those that are missing.
missing_fields = fieldsAbsent(transPts, transect_fields)
if missing_fields:
    join_with_dataframes(extendedTransects, transPts, tID_fld, pID_fld, missing_fields)
    # Save final transect points before moving on to segmenting them
    # arcpy.DeleteField_management(transPts, missing_fields)  # in case reprocessing
    # arcpy.JoinField_management(transPts, tID_fld, extendedTransects,
    #                            tID_fld, missing_fields)

# Save pts as feature class with Nulls (transSplitPts_final)
arcpy.FeatureClassToFeatureClass_conversion(transPts, home, transPts_null)
# Replace Null values with fills and save as FC, SHP, and CSV
arcpy.FeatureClassToFeatureClass_conversion(transPts, home, transPts_fill)
ReplaceValueInFC(transPts_fill, None, fill)
arcpy.FeatureClassToFeatureClass_conversion(transPts_fill, out_dir,
                                            transPts_shp+'.shp')

# arcpy.TableToTable_conversion(transPts_fill, out_dir, transPts_fill+'.csv')
# finalmessage = "The final products ({}) were exported as a shapefile and CSV "\
#                "to {}. \n\nNow enter the USER to save the table: \n\n"\
#                "1. Open the CSV in Excel and then Save as... a .xlsx file. \n"\
#                "2. Open the XLS file in Matlab with the data checking script "\
#                "to check for errors! ".format(transPts_shp, out_dir)
# print(finalmessage)
# pythonaddins.MessageBox(finalmessage, 'Final Steps')

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
