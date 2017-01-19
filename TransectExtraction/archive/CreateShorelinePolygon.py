"""
Create shoreline polygon with Sara's methods as guide:

Converted MHW shoreline points to a line (Points to Line tool)
Created 0-contour line using DEM
- Added MHW conversion raster to study area DEM
- Used Contour tool in ArcToolbox to create 0 contour (contour interval = 1,000; base = 0)
- Smoothed contour using Smooth tool in ArcToolbox (50 m X,Y Tolerance)
Deleted all parts of 0-contour line that overlapped with MHW shoreline
Merged MHW shoreline and clipped 0-contour line; visually inspected new shoreline layer for large gaps (edited lines as necessary to close gaps)
Used Integrate tool in ArcToolbox to close small gaps in new shoreline (1 m X,Y Tolerance)
Used Dissolve tool in ArcToolbox to dissolve line segments into a single line
Closed off full shoreline lines and converted from line to polygon (polygons should show land components of study area)

Reclassify
RasterToPolygon
Union
Dissolve
Densify
Snap
"""

import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *


"""
Cedar
"""
# Inputs
site = 'Cedar'
year = '2014'

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)

MHW = 0.34
MLW = -0.56
MTL = MHW-((MHW-MLW)/2)

elevGrid = '{}{}_DEM'.format(site,year)
bndMHW = '{}{}_bndpoly_mtl'.format(site,year)

# Outputs
RasterToLandPerimeter(elevGrid,bndMHW,MTL)

MHW_oceanside = "{}{}_MHWocean".format(site,year)
barrierBoundary = '{}{}_bndpoly'.format(site,year)
ShorelinePts = '{}{}_SLpts'.format(site,year)

arcpy.PointsToLine_management(ShorelinePts,MHW_oceanside,sort_field='northing')
NewBNDpoly(bndMHW, MHW_oceanside, barrierBoundary, '25 METERS','45 METERS')

arcpy.Union_analysis(barrierBoundary, barrierBoundary+"_union", gaps='NO_GAPS')
arcpy.Dissolve_management(barrierBoundary+'_union',barrierBoundary,multi_part='MULTI_PART')
arcpy.AggregatePolygons_cartography(barrierBoundary, barrierBoundary+'_agg', '30 METERS',
                                    '300 SquareMeters', '300 SquareMeters')

"""
Cobb
"""
site = 'Cobb'
year = '2014'

MHW = 0.34
MLW = -0.59
MTL = MHW-((MHW-MLW)/2)

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)
elevGrid = '{}{}_DEM'.format(site,year)
bndMHW = '{}{}_bndpoly_mtl'.format(site,year)

# Polygon of MHW contour
RasterToLandPerimeter(elevGrid,bndMHW,MTL)
# Compare the bayside shoreline from 2010 with the 2012 imagery and manually modify where they do not match.

bndMHW = '{}{}_bndpoly_mhw'.format(site,year)

# Polygon of MHW contour
RasterToLandPerimeter(elevGrid,bndMHW,MHW)
# Compare the bayside shoreline from 2010 with the 2012 imagery and manually modify where they do not match.


"""
Smith
"""
site = 'Smith'
year = '2014'

MHW = 0.34
MLW = -0.61
MTL = MHW-((MHW-MLW)/2)

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)
elevGrid = '{}{}_DEM'.format(site,year)
bndMHW = '{}{}_bndpoly_mtl'.format(site,year)

# Polygon of MHW contour
RasterToLandPerimeter(elevGrid,bndMHW,MTL)
# Compare the bayside shoreline from 2010 with the 2012 imagery and manually modify where they do not match.

proj_code=26918
inletLines = '{}{}_inletLines'.format(site,year)
arcpy.CreateFeatureclass_management(home,inletLines,'POLYLINE',spatial_reference=arcpy.SpatialReference(proj_code))

MHW_oceanside = "{}{}_MHWocean".format(site,year)
barrierBoundary = '{}{}_bndpoly'.format(site,year)
ShorelinePts = '{}{}_SLpts'.format(site,year)

arcpy.PointsToLine_management(ShorelinePts,MHW_oceanside,'#','northing')
shoreline = site+year+'_ShoreBetweenInlets'
if not arcpy.Exists(shoreline):
    # Create shoreline from MHW_oceanside
    DeleteExtraFields(inletLines)
    DeleteExtraFields(MHW_oceanside)
    MHW_oceanside = ReProject(MHW_oceanside,MHW_oceanside+'_utm',26918)
    # Merge and then extend shoreline to inlet lines
    arcpy.Merge_management([MHW_oceanside,inletLines],'shore_temp')
    arcpy.ExtendLine_edit('shore_temp','500 Meters')
    arcpy.Intersect_analysis([inletLines,'shore_temp'],'xpts_temp','ONLY_FID',output_type='POINT')
    arcpy.SplitLineAtPoint_management('shore_temp','xpts_temp','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", ShorelinePts,'1 METERS') # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
    arcpy.SpatialJoin_analysis('split_temp',inletLines,shoreline,"JOIN_ONE_TO_ONE") # count intersecting inlet lines
    #arcpy.Delete_management(os.path.join(home,'split_temp'))

    ReplaceFields(shoreline,{'ORIG_FID':'OID@'},'SHORT')
else:
    pass



NewBNDpoly(bndMHW, MHW_oceanside, barrierBoundary, '25 METERS','45 METERS')


"""
Plum
"""
site = 'Plum'
year = '2014'

MHW = 1.22
MLW = -1.38
MTL = MHW-((MHW-MLW)/2)

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Massachusetts\{}\{}\{}{}.gdb'.format(site,year,site,year)
elevGrid = '{}{}_DEM'.format(site,year)
bndMHW = '{}{}_bndpoly_mtl'.format(site,year)

# Polygon of MHW contour
RasterToLandPerimeter(elevGrid,bndMHW,MTL)
# Compare the bayside shoreline from 2010 with the 2012 imagery and manually modify where they do not match.

"""
Crane
"""
site = 'CI'
year = '2014'

MHW = 1.22
MLW = -1.38
MTL = MHW-((MHW-MLW)/2)

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)
elevGrid = '{}{}_DEM'.format(site,year)
bndMHW = '{}{}_bndpoly_mtl'.format(site,year)

# Polygon of MHW contour
RasterToLandPerimeter(elevGrid,bndMHW,MTL)
# Compare the bayside shoreline from 2010 with the 2012 imagery and manually modify where they do not match.




# Smooth - doesn't change any of the problems - just makes it look nicer.
RUDpoly = 'PI2014_bndpoly_mhw'
arcpy.SmoothPolygon_cartography(RUDpoly,'PI2014bndpoly_RUDSmooth_PAEK50_temp',"PAEK",'50 METERS')


# Points to Line: ShorelinePts => MHWoceanside
arcpy.PointsToLine_management(ShorelinePts, MHW_oceanside,Sort_Field="lat")



"""
Crane
"""
ShorelinePts='Crane2014_SLpts'
MHW_oceanside = 'Crane2014_oceanside'
arcpy.Sort_management(ShorelinePts,ShorelinePts+'_sort',"lat")
with arcpy.da.UpdateCursor(ShorelinePts+'_sort',["OBJECTID","OID"]) as cursor:
    for row in cursor:
        cursor.updateRow([row[0], row[0]])
arcpy.PointsToLine_management(ShorelinePts, MHW_oceanside,Sort_Field="OID")
NewBNDpoly(bndMMMdissolve,MHW_oceanside,bndwithMHWocean,'50 METERS','90 METERS')


# barrierBoundary from 0m elevation
bnd0m = barrierBoundary+'_0m'
RasterToLandPerimeter(elevGrid,bnd0m,0.0)
arcpy.Union_analysis([manualadditions,bndMHW,bnd0m],barrierBoundary+'_temp',gaps='NO_GAPS')
# Select only the corrects parts to include within boundary
arcpy.Dissolve_management(barrierBoundary+'_temp',barrierBoundary+'_0mout',multi_part='MULTI_PART')



# Run
RasterToLandPerimeter(elevGrid,bndMHW,MHW)
if manualadditions:  # Manually digitized any large areas missed by the lidar
    arcpy.Union_analysis([manualadditions, bndMHW, 'FI2011_Marsh'], bndMMM, gaps='NO_GAPS')
    arcpy.Dissolve_management(bndMMM, bndMMMdissolve, multi_part='SINGLE_PART')
else:
    bndMMMdissolve = bndMHW  # Fill in gaps in the island interior


# Delete extra land

# Smooth (optionally) (50 m X,Y Tolerance



# Integrate image classification results to make up for missing lidar
rastertemp=arcpy.sa.Con('cedar12_class',1,None,'"ORIGINALCLASS"="Marsh"') # Doesn't work and I'm not sure why.
# do this in ArcMap

rastertemp=arcpy.sa.Con(arcpy.sa.Raster('Cedar2012_MarshRaster')==1,1,"") # replace 0 values with Null
# maybe run a filtering routine here

in_raster = 'class_test1_temp'
rastertemp = arcpy.sa.Con(arcpy.sa.Raster(in_raster)==1,1,"")
arcpy.RasterToPolygon_conversion(rastertemp, 'marsh_r2p_temp')

arcpy.SelectLayerByLocation_management('marsh_r2p_temp',)
arcpy.Union_analysis('marsh_r2p_temp', 'r2p_sel_union_temp', gaps='NO_GAPS')


arcpy.Union_analysis('marsh_r2p_temp', 'r2p_union_temp', gaps='NO_GAPS')
arcpy.Dissolve_management('r2p_union_temp', 'r2p_union_diss_temp', multi_part='MULTI_PART')
arcpy.AggregatePolygons_cartography('r2p_union_diss_temp', 'r2p_union_diss_agg_temp', '30 METERS',
                                        '300 SquareMeters', '300 SquareMeters')

CreateShoreBetweenInlets(SLpts,inletLines,out_line,proj_code=26918)


# Mosaic MHW reclass and 0m reclass rasters before creating polygons
mhw_temp = arcpy.sa.Con(arcpy.sa.Raster(old_dem)>MHW, 1, 0)
zero_temp = arcpy.sa.Con(arcpy.sa.Raster(alt_dem)>0, 1, 0)
# Clip zero_temp to bayside only (marsh)
land_zone = "{}{}_LandZone".format(site,year)
arcpy.Buffer_analysis(shoreline,land_zone,'4000 Meters','Left')
masked_dem = arcpy.sa.ExtractByMask(zero_temp,land_zone)

arcpy.MosaicToNewRaster_management([masked_dem,mhw_temp],home,'ReMaskMos_temp',"","32_BIT_FLOAT","",1,"LAST")
ReMaskMosRe_temp=arcpy.sa.Con(arcpy.sa.Raster('ReMaskMos_temp')==1,1,"")

arcpy.RasterToPolygon_conversion(ReMaskMosRe_temp, 'ReMaskMosRe_r2p_temp')
arcpy.AggregatePolygons_cartography('ReMaskMosRe_r2p_temp', 'ReMaskMosRe_r2pAgg_temp', '30 METERS',
                                    '300 SquareMeters', '300 SquareMeters')
arcpy.Union_analysis('ReMaskMosRe_r2pAgg_temp', 'ReMaskMosRe_r2pAggUn_temp', gaps='NO_GAPS')
arcpy.Dissolve_management('ReMaskMosRe_r2pAggUn_temp', 'ReMaskMosRe_r2pAggUnDis_temp', multi_part='MULTI_PART')
arcpy.MultipartToSinglepart_management('ReMaskMosRe_r2pAggUnDis_temp','ReMaskMosRe_r2pAggUnDisSing_temp')

NewBNDpoly('ReMaskMosRe_r2pAggUnDis_temp',ShorelinePts,'ReMaskMosRe_r2pAggUnDis_edit2SLpts_temp','25 METERS','50 METERS')






arcpy.RasterToPolygon_conversion(ReMosRe_temp, 'ReMos_r2p_temp')
arcpy.Union_analysis('ReMos_r2p_temp', 'ReMos_r2p_union_temp', gaps='NO_GAPS')
arcpy.Dissolve_management('ReMos_r2p_union_temp', 'ReMos_r2p_uniondiss_temp', multi_part='MULTI_PART')
arcpy.AggregatePolygons_cartography('ReMos_r2p_uniondiss_temp', 'ReMos_r2p_uniondiss_agg_temp', '30 METERS',
                                    '300 SquareMeters', '300 SquareMeters')
arcpy.MultipartToSinglepart_management('ReMos_r2p_uniondiss_agg_temp','ReMos_r2p_uniondiss_aggsing_temp')

arcpy.MultipartToSinglepart_management('ReMos_r2p_uniondiss_temp','ReMos_r2p_uniondisssing_temp')
arcpy.AggregatePolygons_cartography('ReMos_r2p_temp', 'ReMos_r2p_agg_temp', '30 METERS',
                                    '300 SquareMeters', '300 SquareMeters')

