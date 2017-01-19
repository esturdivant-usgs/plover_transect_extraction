"""
Create shoreline polygon for Forsythe 2012 because requires individualized attention.

Modified from Pre_CreateShorelinePoly on 10/12
"""

import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

start = time.clock()

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
#arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
############ Inputs #########################
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2012',
                    'region': 'NewJersey',
                    'MHW':0.43,
                    'MLW':-0.61}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(
    **SiteYear_strings)
out_dir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)

deletePtsWithZfill = False          # If True, dune points with elevations of fill (-99999) will be deleted
CreateMHWline = False
rawtransects = False
rawbarrierline = 'LI_BND_2012Line'
transUIDfieldname = "trans_sort"

########### Automatic population ###########
MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
extendedTransects = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt
ShorelinePts = '{site}{year}_SLpts'.format(**SiteYear_strings)
dhPts = '{site}{year}_DHpts'.format(**SiteYear_strings)				# Dune crest
dlPts = '{site}{year}_DLpts'.format(**SiteYear_strings) 				# Dune toe
MHW_oceanside = "{site}{year}_MHWfromSLPs".format(**SiteYear_strings)
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings)             # manually create lines based on the boundary polygon that correspond to end of land and cross the MHW line
armorLines = '{site}{year}_armor'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_bndpoly_2sl'.format(**SiteYear_strings)   # Barrier Boundary polygon; create with TE_createBoundaryPolygon.py
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)				# Elevation
elevGrid_5m = elevGrid+'_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat

########### Default Values ##########################
dMHW = -MHW                    # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
MTL = MHW-(MLW/2)
fill = -99999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
extendlength = 3000                      # extended transects distance (m) IF NEEDED
if SiteYear_strings['region'] == 'Massachusetts' or SiteYear_strings['region'] == 'RhodeIsland' or SiteYear_strings['region'] == 'Maine':
    proj_code = 26919 # "NAD 1983 UTM Zone 19N"
    utmSR = arcpy.SpatialReference(proj_code)
else:
    proj_code = 26918 # "NAD 1983 UTM Zone 18N"
    utmSR = arcpy.SpatialReference(proj_code)

############## Outputs ###############################
dh2trans = '{site}{year}_DH2trans'.format(**SiteYear_strings)							# DHigh within 10m
dl2trans = '{site}{year}_DL2trans'.format(**SiteYear_strings)						# DLow within 10m
arm2trans = '{site}{year}_arm2trans'.format(**SiteYear_strings)
oceanside_auto = '{site}{year}_MHWfromSLPs'.format(**SiteYear_strings)
shl2trans = '{site}{year}_SHL2trans'.format(**SiteYear_strings)							# beach slope from lidar within 10m of transect
MLWpts = '{site}{year}_MLW2trans'.format(**SiteYear_strings)                     # MLW points calculated during Beach Width calculation
shoreline = '{site}{year}_ShoreBetweenInlets'.format(**SiteYear_strings)        # Complete shoreline ready to become route in Pt. 2
slopeGrid = '{site}{year}_slope5m'.format(**SiteYear_strings)
baseName = 'trans_clip_working'                    # Clipped transects
transects_part2 = os.path.join(home,'trans_part2')
transects_final = '{site}{year}_trans_populated'.format(**SiteYear_strings)
tranSplitPts = '{site}{year}_transPts_working'.format(**SiteYear_strings) 	# Outputs Transect Segment points
tranSplitPts_null = '{site}{year}_transPts_null'.format(**SiteYear_strings)
tranSplitPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)
tranSplitPts_shp = '{site}{year}_transPts_shp'.format(**SiteYear_strings)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')

tempfile = 'trans_temp'
armz = 'Arm_z'

# Check presence of default files in gdb
extendedTransects = SetInputFCname(home, 'extendedTransects', extendedTransects)
inletLines = SetInputFCname(home, 'inlet lines (inletLines)', inletLines)
#armorLines = SetInputFCname(home, 'beach armoring lines (armorLines)', armorLines)

"""
Process: Land perimeter front and back
"""
def RasterToLandPerimeter(in_raster,out_polygon,threshold,agg_dist='30 METERS',min_area='300 SquareMeters',min_hole_sz='300 SquareMeters',manualadditions=None):
    """ Raster to Polygon: DEM => Reclass => MHW line """
    home = arcpy.env.workspace
    r2p = os.path.join(home, out_polygon+'_r2p_temp')
    r2p_union = os.path.join(home, out_polygon+'_r2p_union_temp')

    if not arcpy.Exists(r2p):
        # Reclassify DEM to 1-land NoData-all else and convert to polygon
        rastertemp = arcpy.sa.Con(arcpy.sa.Raster(in_raster)>threshold, 1, None)
        arcpy.RasterToPolygon_conversion(rastertemp, r2p)  # polygon outlining the area above MHW
    if manualadditions:
        # Manually digitized any large areas missed by the lidar
        arcpy.Union_analysis(manualadditions+[r2p], r2p_union, gaps='NO_GAPS')
        arcpy.AggregatePolygons_cartography(r2p_union, out_polygon, agg_dist, min_area, min_hole_sz)
    else:
        arcpy.AggregatePolygons_cartography(r2p, out_polygon, agg_dist, min_area, min_hole_sz)
    return out_polygon

def DEMtoFullShorelinePoly(elevGrid,prefix,MTL,MHW,inletLines,ShorelinePts, backbarrier_additions=None):
    bndMTL = '{}_bndpoly_mtl'.format(prefix)
    bndMHW = '{}_bndpoly_mhw'.format(prefix)
    bndpoly = '{}_bndpoly'.format(prefix)

    RasterToLandPerimeter(elevGrid, bndMTL, MTL, manualadditions=backbarrier_additions)  # Polygon of MTL contour
    RasterToLandPerimeter(elevGrid, bndMHW, MHW)  # Polygon of MHW contour
    CombineShorelinePolygons(bndMTL, bndMHW, inletLines, ShorelinePts, bndpoly)

    #DeleteTempFiles()
    return bndpoly

prefix = '{site}{year}'.format(**SiteYear_strings)
out_polygon = bndMTL = '{}_bndpoly_mtl'.format(prefix)
bndMHW = '{}_bndpoly_mhw'.format(prefix)
bndpoly = '{}_bndpoly'.format(prefix)

manadd = ['Forsythe2012_Development','Forsythe2012_Marsh']

arcpy.Project_management(r2p,r2p+'_utm',utm18n,)
r2p=r2p+'_utm'

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
