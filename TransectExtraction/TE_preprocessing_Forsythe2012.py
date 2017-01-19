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
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension

"""
SET VALUES
"""
# same as TE
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2014',
                    'region': 'NewJersey',
                    'MHW':0.43,
                    'MLW':-0.61}

arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)
proj_code=26918
site = '{site}'.format(**SiteYear_strings)
MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
MTL = MHW-((MHW-MLW)/2)

# not in TE
DHdir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\beach_metrics\Kathy_dhighs'.format(**SiteYear_strings)
DLdir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\beach_metrics\Kathy_dlows'.format(**SiteYear_strings)
old_dem = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\lidar\AssawomanIsland_USGS_lidar_2012.tif'.format(**SiteYear_strings)
old_transects = '{site}_LTtransects_clip'.format(**SiteYear_strings)

# Outputs
ShorelinePts = '{site}{year}_SLpts'.format(**SiteYear_strings)
dhPts = '{site}{year}_DHpts'.format(**SiteYear_strings)				# Dune crest
dlPts = '{site}{year}_DLpts'.format(**SiteYear_strings) 				# Dune toe
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)

MHW_oceanside = "{site}{year}_MHWocean".format(**SiteYear_strings)
shoreline = "{site}{year}_ShoreBetweenInlets".format(**SiteYear_strings)
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)
bndpoly = '{site}{year}_bndpoly'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_bndpoly_2sl'.format(**SiteYear_strings)

# Transect processing
in_fc = 'Forsythe_extTrans_v2'
base_fc = 'Forsythe_extTrans_v3'
sortfield = 'trans_sort'
sort_corner='LL'

"""
PROCESSING
"""
arcpy.CreateFeatureclass_management(home,'sort_line1', "POLYLINE", projCR)
arcpy.CopyFeatures_management('sort_line1','{}\\sort_line2'.format(home))
sort_line_list = ['sort_line1','sort_line2']

SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield='trans_sort',sort_corner='LL')

# To be completed after manual steps to fill gaps, making sure that the new transects have null values
# Split the set of transects to ensure that the sort from __ corner is accurate.
extTransects = PreprocessTransects(site,old_transects,sort_corner='LL')

##### Merge beach metrics #####
dhPts = SetInputFCname(home, 'barrier island polygon (barrierBoundary)', dhPts, False)
if not dhPts:
    arcpy.env.workspace = DHdir
    outfile = r"{}\{}".format(home,dhPts)
    arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

dhPts = SetInputFCname(home, 'barrier island polygon (barrierBoundary)', dhPts, False)
if not dhPts:
    arcpy.env.workspace = DLdir
    outfile = r"{}\{}".format(home,dlPts)
    arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

# arcpy.env.workspace = DHdir
# outfile = r"{}\{}".format(home,dhPts)
# arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

# arcpy.env.workspace = DLdir
# outfile = r"{}\{}".format(home,dlPts)
# arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)

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
