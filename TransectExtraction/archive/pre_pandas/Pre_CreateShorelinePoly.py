"""
Create shoreline polygon

Looks like the most updated version as of 10/12/16
"""

import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

"""
Inputs
"""
SiteYear_strings = {'site':'CapeHatteras',
                    'year':'2014',
                    'region':'NorthCarolina'}
MHW = 0.26 # Delmarva value from Weber,
MLW = -.45 #  MLW in NAVD88 according to Ben
utm18 = arcpy.SpatialReference(26918)

# AUTOMATIC INPUTS
arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)
out_dir = r'T:\Commons_DeepDive\DeepDive\4Sara'.format(**SiteYear_strings)

MTL = MHW-((MHW-MLW)/2)
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)
ShorelinePts = '{site}{year}_SLpts'.format(**SiteYear_strings)
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)
DHpts = '{site}{year}_DHpts'.format(**SiteYear_strings)
DLpts = '{site}{year}_DLpts'.format(**SiteYear_strings)

# OUTPUTS
#elevGrid = r'T:\Commons_DeepDive\DeepDive\NewJersey\Forsythe\2014\lidar\{site}{year}_NOAA_DEM.tif'.format(**SiteYear_strings)
bndpoly = '{site}{year}_bndpoly'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_bndpoly_2sl'.format(**SiteYear_strings)

"""
Process: Land perimeter front and back
"""
if len(arcpy.ListFeatureClasses(inletLines))<1:
    arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=utm18)
    exit()

DEMtoFullShorelinePoly(elevGrid,'{site}{year}'.format(**SiteYear_strings),MTL,MHW,inletLines,ShorelinePts)

# Eliminate any remnant polygons on oceanside
if pythonaddins.MessageBox('Ready to delete selected features?','',4) == 'Yes':
    arcpy.DeleteFeatures_management(bndpoly)
else:
    print 'Ok, redo.'
    exit()
# Snap oceanside to ShorelinePts?
NewBNDpoly(bndpoly,ShorelinePts,barrierBoundary,'25 METERS','50 METERS')

arcpy.FeatureClassToFeatureClass_conversion(DHpts,out_dir,DHpts+'.shp')
arcpy.FeatureClassToFeatureClass_conversion(DLpts,out_dir,DLpts+'.shp')
arcpy.FeatureClassToFeatureClass_conversion(ShorelinePts,out_dir,ShorelinePts+'.shp')
arcpy.FeatureClassToFeatureClass_conversion(barrierBoundary,out_dir,barrierBoundary+'.shp')

"""
IN_strings = {'elevGrid':'{site}{year}_DEM'.format(**SiteYear_strings),
              'barrierBoundary':'{site}{year}_bndpoly_2sl'.format(**SiteYear_strings),
              'ShorelinePts':'{site}{year}_SLpts'.format(**SiteYear_strings),
              'inletLines':'{site}{year}_inletLines'.format(**SiteYear_strings)}

bndMTL = '{site}{year}_bndpoly_mtl'.format(**SiteYear_strings)
bndMHW = '{site}{year}_bndpoly_mhw'.format(**SiteYear_strings)
bndpoly = '{site}{year}_bndpoly'.format(**SiteYear_strings)

RasterToLandPerimeter(elevGrid, bndMHW, MHW)  # Polygon of MHW contour
RasterToLandPerimeter(elevGrid, bndMTL, MTL)  # Polygon of MTL contour
CombineShorelinePolygons(bndMTL, bndMHW, inletLines, ShorelinePts, bndpoly)
"""

# Other processing

SiteYear_strings = {'site': 'Chincoteague',
                    'year': '2014',
                    'region': 'Delmarva'}
#out_dir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)
out_dh = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb\{site}{year}_DHpts'.format(**SiteYear_strings)
arcpy.CopyFeatures_management("VA_points\VA_14CNT01_dhigh",out_dh)
out_dl = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb\{site}{year}_DLpts'.format(**SiteYear_strings)
arcpy.CopyFeatures_management("VA_points\VA_14CNT01_dlow",out_dl)
out_sl = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb\{site}{year}_SLpts'.format(**SiteYear_strings)
arcpy.CopyFeatures_management("VA_points\VA_14CNT01_shoreline",out_sl)
