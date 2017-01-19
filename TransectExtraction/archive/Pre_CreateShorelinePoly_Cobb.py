"""
Create shoreline polygon
"""

import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

"""
Inputs
"""
site = 'Cobb'
year = '2014'

MHW = 0.34
MLW = -0.59
MTL = MHW-((MHW-MLW)/2)

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)
elevGrid = '{}{}_DEM'.format(site,year)
bndMTL = '{}{}_bndpoly_mtl'.format(site,year)
bndMHW = '{}{}_bndpoly_mhw'.format(site,year)
bndpoly = '{}{}_bndpoly'.format(site,year)
barrierBoundary = '{}{}_bndpoly_2sl'.format(site,year)

ShorelinePts = '{}{}_SLpts'.format(site,year)
inletLines = '{}{}_inletLines'.format(site,year)

union_mhwmtl = 'union_mtlmhw_temp'.format(site,year)
split_temp = 'split_union2inlets_temp'
union_2 = 'union_mtlmhw_2_temp'

"""
Process: Land perimeter front and back
"""
def DEMtoFullShorelinePoly(elevGrid,prefix,MTL,MHW):
    bndMTL = '{}_bndpoly_mtl'.format(prefix)
    bndMHW = '{}_bndpoly_mhw'.format(prefix)
    bndpoly = '{}_bndpoly'.format(prefix)

    union = 'union_temp'
    split_temp = 'split_temp'
    union_2 = 'union_2_temp'

    RasterToLandPerimeter(elevGrid, bndMTL, MTL)  # Polygon of MTL contour
    RasterToLandPerimeter(elevGrid, bndMHW, MHW)  # Polygon of MHW contour

    arcpy.Union_analysis([bndMTL, bndMHW], union)
    query = 'FID_{}>0 AND FID_{}<0'.format(bndMTL, bndMHW)
    arcpy.SelectLayerByAttribute_management(union, 'NEW_SELECTION', query)
    # Split MTL features at inlets
    arcpy.FeatureToPolygon_management([union, inletLines], split_temp)
    arcpy.DeleteFeatures_management(union)  # Delete MTL features of union
    # Delete oceanside MTL features
    arcpy.SelectLayerByLocation_management(split_temp, "INTERSECT", ShorelinePts, '#', "NEW_SELECTION")
    arcpy.DeleteFeatures_management(split_temp)
    # Union remaining MTL features with original union
    arcpy.Union_analysis([split_temp, union_mhwmtl], union_2)
    arcpy.Dissolve_management(union_2, bndpoly, multi_part='SINGLE_PART')
    return bndpoly

DEMtoFullShorelinePoly(elevGrid,prefix,MTL,MHW)

message = 'Recommended technique: select the polygon/s to keep and then Switch Selection'
pythonaddins.MessageBox(message, 'Select extra features for deletion')

if pythonaddins.MessageBox('Ready to delete selected features?','',4) == 'Yes':
    # Eliminate any remnant polygons on oceanside
    arcpy.DeleteFeatures_management(bndpoly)
else:
    print 'Ok, redo.'



RasterToLandPerimeter(elevGrid,bndMTL,MTL) # Polygon of MTL contour
RasterToLandPerimeter(elevGrid,bndMHW,MHW) # Polygon of MHW contour

arcpy.Union_analysis([bndMTL,bndMHW],union_mhwmtl)
query = 'FID_{}>0 AND FID_{}<0'.format(bndMTL,bndMHW)
arcpy.SelectLayerByAttribute_management(union_mhwmtl,'NEW_SELECTION',query)
# Split MTL features at inlets
arcpy.FeatureToPolygon_management([union_mhwmtl,inletLines],split_temp)
arcpy.DeleteFeatures_management(union_mhwmtl) # Delete MTL features of union
# Delete oceanside MTL features
arcpy.SelectLayerByLocation_management(split_temp,"INTERSECT",ShorelinePts,'#',"NEW_SELECTION")
# How to also select features outside of inlet lines?
arcpy.DeleteFeatures_management(split_temp)
# Union remaining MTL features with original union
arcpy.Union_analysis([split_temp,union_mhwmtl],union_2)
arcpy.Dissolve_management(union_2,bndpoly,multi_part='SINGLE_PART')






"""
Process: modify front to shoreline points
"""
NewBNDpoly(bndpoly,ShorelinePts,barrierBoundary,'25 METERS','25 METERS')
