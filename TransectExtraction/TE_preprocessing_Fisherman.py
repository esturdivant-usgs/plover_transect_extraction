"""
Created by: Emily Sturdivant (esturdivant@usgs.gov)
Date: April 11, 2016


This routine preprocesses layers for use in TransectExtraction, including:
- DEM - saves the projected 1m resolution DEM in siteyear gdb and produces 5m resolution DEM as well
- full shoreline polygon = MHW isoline from DEM
- extended transects with correctly sorted TransOrder IDs

Steps before running:
- confirm/modify the location of the original DEM
- create a siteyear gdb if it does not already exist

- from the original transects file, save the transects pertaining to the site as [Site]_LTtransects.
- manually edit the LTtransects to add transects to gaps
"""

import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *
from TE_config_Fisherman2014 import *

"""
SET VALUES
"""
# not in TE
DHdir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\beach_metrics\{site}{year}_dhighs_segs01_09'.format(**SiteYear_strings)
DLdir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\beach_metrics\{site}{year}_dlows_segs01_09'.format(**SiteYear_strings)
SLdir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\beach_metrics\{site}{year}_shorelines_segs01_09'.format(**SiteYear_strings)
old_dem = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\lidar\Monomoy1314_USGS_DEM.tif'.format(**SiteYear_strings)
old_transects = '{site}S_SVA_LT.shp'.format(**SiteYear_strings)

# Transect processing
transects_presort = '{home}\\{site}_transects_presort'.format(**SiteYear_strings)
#in_fc = 'Forsythe_extTrans_v2'
#base_fc = 'Forsythe_extTrans_v3'
sortfield = 'sort_ID'
# How to choose sort_corner:
sort_corner='LL'

"""
PROCESSING
"""
# TRANSECTS
new_transects = "Fisherman_transects_presort_utm"
old_transects = r"\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\Delmarva\Fisherman\2014\Fisherman2014.gdb\Delmarva_SVA_LT_fisherman"
extendedTransects = "Delmarva_SVA_LT_fisherman_extended"
trans_temp = rawtransects+"_temp"

rawtransects = SetInputFCname(home, 'Raw transects', 'rawtransects')
# Extend original transects if not already
if arcpy.Exists(gen_bay_line):
    # Select lines based on azimuth... so that they will not end up intersecting each other.
    # Select lines that still need to be extended. Include in selection the generalized bay line.
    arcpy.Merge_management([rawtransects, gen_bay_line],trans_temp)
    #arcpy.CopyFeatures_management(rawtransects, trans_temp)
    arcpy.ExtendLine_edit(trans_temp, extend_to="FEATURE")
    # un-select generalized bay line
    arcpy.DeleteFeatures_management(rawtransects)
    arcpy.Append_management(trans_temp, rawtransects)
    exit()
else:
    ExtendLine(rawtransects,extendedTransects,extendlength,proj_code)
    if len(arcpy.ListFields(extendedTransects,'OBJECTID*')) == 2:
        ReplaceFields(extendedTransects,{'OBJECTID':'OID@'})

old_transects = SetInputFCname(home, 'Original National Assessment Transects', old_transects)
# Make copy of transects and manually fill the gaps. Then select all the new transect and run the next piece of code.
arcpy.CopyFeatures_management(old_transects,transects_presort)
# Replace values of all new transects
tranFields = []
for f in arcpy.ListFields(new_transects):
    tranFields.append(f.name)
with arcpy.da.UpdateCursor(new_transects, tranFields[2:]) as cursor:
    for row in cursor:
        cursor.updateRow([None] * len(row))
pythonaddins.MessageBox("Copy existing groups of transects to fill int he gaps. Leave new transects protuding slightly from line so that you can identify them. Clip any overlapping transects. Select the new transects and proceed. Okay?", "Created {}. Proceed with manual processing.".format(transects_presort), 0)
exit()

# Delete any NAT transects in the new transects layer
arcpy.SelectLayerByLocation_management(new_transects, "ARE_IDENTICAL_TO", old_transects) # or "SHARE_A_LINE_SEGMENT_WITH"
if int(arcpy.GetCount_management(new_transects)[0]) > 0:
    arcpy.DeleteFeatures_management(new_transects) # if there are old transects in new transects, delete them
# Append relevant NAT transects to the new transects
arcpy.SelectLayerByLocation_management(old_transects, "INTERSECT", barrierBoundary)
arcpy.Append_management(old_transects, new_transects)


# Sort and add unique ID
# Create field sort_ID and sort by that
trans_presort = "Fisherman_transects_presort_utm"
trans_sort_1 = "Fisherman_transects_sorted"
# Select first batch (48)
trans_sort_1, count1 = SpatialSort(trans_presort,trans_sort_1,"LR",reverse_order=True,sortfield="sort_ID")
# Select second batch
trans_sort_2 = "transects_sort2"
# azimuth >
trans_sort_2, count2 = SpatialSort(trans_presort,trans_sort_2,"LR",reverse_order=True, startcount=count1)
#arcpy.Append_management(trans_sort_2, trans_sort_1)
# Select third batch
trans_sort_3 = "transects_sort3"
startcount=count1+count2
trans_sort_3, count3 = SpatialSort(trans_presort,trans_sort_3,"LL",reverse_order=False, startcount=startcount)
#arcpy.Append_management(trans_sort_3, trans_sort_1)
# Select fourth batch
trans_sort_4 = "transects_sort4"
startcount=count1+count2+count3
trans_sort_4, count4 = SpatialSort(trans_presort,trans_sort_4,"LL",reverse_order=False,startcount=startcount)
arcpy.Append_management([trans_sort_2, trans_sort_3, trans_sort_4], trans_sort_1)

arcpy.Sort_management(trans_sort_1, extendedTransects, [['SORT_ID','ASCENDING']])

"""
Previous code
"""
#### Prepare transects ####
# Make copy of transects and manually fill the gaps. Then select all the new transect and run the next piece of code.
arcpy.CopyFeatures_management(old_transects,transects_presort)

# Replace values of copied transects with Null.
with arcpy.da.UpdateCursor(transects_presort, ['OBJECTID','TRANSORDER','LRR','LR2','LSE','LCI90']) as cursor:
    for row in cursor:
        cursor.updateRow([None, None, None, None, None, None])

# To be completed after manual steps to fill gaps, making sure that the new transects have null values
# Split the set of transects to ensure that the sort from __ corner is accurate.
extTransects = PreprocessTransects(site,old_transects,sort_corner='LL')

# Experimental alternative:
# Create lines to use to sort new transects
arcpy.CreateFeatureclass_management(home,'sort_line1', "POLYLINE", spatial_reference=arcpy.SpatialReference(proj_code))
arcpy.CopyFeatures_management('sort_line1','{}\\sort_line2'.format(home))
sort_line_list = ['sort_line1','sort_line2']

SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield=transUIDfield,sort_corner='LL')

##### Merge beach metrics #####
arcpy.env.workspace = DHdir
outfile = r"{}\{}".format(home,dhPts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

arcpy.env.workspace = DLdir
outfile = r"{}\{}".format(home,dlPts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

arcpy.env.workspace = SLdir
outfile = r"{}\{}".format(home,ShorelinePts)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

# DEM
elevGrid = ProcessDEM(site,year,old_dem,proj_code)

# Full shoreline
RasterToLandPerimeter(elevGrid,bndMHW,MHW)

# Inlet lines
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)
arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=arcpy.SpatialReference(proj_code))

"""
arcpy.Sort_management(ShorelinePts,ShorelinePts+'_sort',"lat")
with arcpy.da.UpdateCursor(ShorelinePts+'_sort',["OBJECTID","OID"]) as cursor:
    for row in cursor:
        cursor.updateRow([row[0], row[0]])
"""
#arcpy.PointsToLine_management(ShorelinePts, MHW_oceanside,Sort_Field="OID")
CreateShoreBetweenInlets(ShorelinePts,inletLines,shoreline,proj_code=26918)


NewBNDpoly(bndMHW,ShorelinePts,barrierBoundary,'25 METERS','25 METERS')
