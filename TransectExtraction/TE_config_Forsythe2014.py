'''
Configuration file for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 11/22/2016
'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

############ Inputs #########################
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2014',
                    'region': 'NewJersey',
                    'MHW':0.43,
                    'MLW':-0.61,
                    'MTL':None}

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 						# Overwrite output?
arcpy.CheckOutExtension("Spatial") 						# Checkout Spatial Analysis extension

CreateMHWline = False
rawtransects = False

plover_rst_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\Zeigler_analysis\Layers_for_BN\{year}\BaseLayers'.format(
    **SiteYear_strings)
arcpy.env.workspace = plover_rst_dir
cellsize_rst = os.path.join(plover_rst_dir, arcpy.ListRasters()[0])

########### Automatic population ###########
arcpy.env.workspace = home = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format( **SiteYear_strings)
SiteYear_strings['home'] = home
out_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)
archive_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\All_Years\{site}_transects.gdb'.format(**SiteYear_strings)

MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
dMHW = -MHW                         # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
SiteYear_strings['MTL'] = MTL = (MHW+MLW)/2

trans_orig = os.path.join(archive_dir, '{site}_extTrans'.format(**SiteYear_strings))
extendedTrans = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt
ShorelinePts = '{site}{year}_SLpts'.format(**SiteYear_strings)
dhPts = '{site}{year}_DHpts'.format(**SiteYear_strings)				# Dune crest
dlPts = '{site}{year}_DLpts'.format(**SiteYear_strings) 		  # Dune toe
MHW_oceanside = "{site}{year}_MHWfromSLPs".format(**SiteYear_strings)
inletLines = '{site}{year}_inletLines'.format(**SiteYear_strings) # manually create lines based on the boundary polygon that correspond to end of land and cross the MHW line
armorLines = '{site}{year}_armor'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_bndpoly_2sl'.format(**SiteYear_strings)   # Barrier Boundary polygon; create with TE_createBoundaryPolygon.py
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)				# Elevation
elevGrid_5m = elevGrid+'_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat

############## Outputs ###############################
extendedTransects = '{site}{year}_extTrans_working'.format(**SiteYear_strings)
dh2trans = '{site}{year}_DH2trans'.format(**SiteYear_strings)							# DHigh within 10m
dl2trans = '{site}{year}_DL2trans'.format(**SiteYear_strings)						# DLow within 10m
arm2trans = '{site}{year}_arm2trans'.format(**SiteYear_strings)
oceanside_auto = '{site}{year}_MHWfromSLPs'.format(**SiteYear_strings)
shl2trans = '{site}{year}_SHL2trans'.format(**SiteYear_strings)							# beach slope from lidar within 10m of transect
MLWpts = '{site}{year}_MLW2trans'.format(**SiteYear_strings)                     # MLW points calculated during Beach Width calculation
CPpts = '{site}{year}_topBeachEdgePts'.format(**SiteYear_strings)                     # Points used as upper beach edge for Beach Width and height
shoreline = '{site}{year}_ShoreBetweenInlets'.format(**SiteYear_strings)        # Complete shoreline ready to become route in Pt. 2
slopeGrid = '{site}{year}_slope_5m'.format(**SiteYear_strings)

extTrans_tidy = "{site}{year}_tidyTrans".format(**SiteYear_strings)
transects_part2 = os.path.join(home,'trans_part2')
transects_final = '{site}{year}_trans_populated'.format(**SiteYear_strings)
transPts = '{site}{year}_transPts_working'.format(**SiteYear_strings) 	# Outputs Transect Segment points
tranSplitPts_null = '{site}{year}_transPts_null'.format(**SiteYear_strings)
tranSplitPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)
tranSplitPts_shp = '{site}{year}_transPts_shp'.format(**SiteYear_strings)
tranSplitPts_bw = '{site}{year}_transPts_beachWidth_fill'.format(**SiteYear_strings)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')
out_stats = os.path.join(home,"avgZ_byTransect")
extTrans_tidy_archive = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SiteYear_strings))
beachwidth_rst = "{site}{year}_beachWidth".format(**SiteYear_strings)

transPts_presort = 'transPts_presort'

rst_transID = "{site}{year}_rstTransID".format(**SiteYear_strings)
rst_transPopulated = "{site}{year}_rstTrans_populated".format(**SiteYear_strings)
rst_trans_grid = "{code}_trans".format(**SiteYear_strings)

########### Default Values ##########################
transUIDfield = "sort_ID"
fill = 9999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
if SiteYear_strings['site'] == 'Monomoy':
    maxDH = 3
else:
    maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
extendlength = 3000                      # extended transects distance (m) IF NEEDED
if SiteYear_strings['region'] == 'Massachusetts' or SiteYear_strings['region'] == 'RhodeIsland' or SiteYear_strings['region'] == 'Maine':
    proj_code = 26919 # "NAD 1983 UTM Zone 19N"
    utmSR = arcpy.SpatialReference(26919)
else:
    proj_code = 26918 # "NAD 1983 UTM Zone 18N"
    utmSR = arcpy.SpatialReference(proj_code)

########### Field names ##########################
transect_fields_part0 = ['sort_ID','TRANSORDER', 'TRANSECTD', 'LRR', 'LR2', 'LSE', 'LCI90']
transect_fields_part1 = ['SL_Lat', 'SL_Lon', 'SL_x', 'SL_y', 'Bslope',
    'DL_Lat', 'DL_Lon', 'DL_x', 'DL_y', 'DL_z', 'DL_zMHW',
    'DH_Lat', 'DH_Lon', 'DH_x', 'DH_y', 'DH_z', 'DH_zMHW',
    'Arm_Lat', 'Arm_Lon', 'Arm_x', 'Arm_y', 'Arm_z', 'Arm_zMHW',
    'DistDH', 'DistDL', 'DistArm']
transect_fields_part2 = ['MLW_x','MLW_y',
   'bh_mhw','bw_mhw',
   'bh_mlw','bw_mlw',
   'CP_x','CP_y','CP_zMHW']
transect_fields_part3 = ['Dist2Inlet']
transect_fields_part4 = ['WidthPart', 'WidthLand', 'WidthFull']
transect_fields = transect_fields_part1 + transect_fields_part2 + transect_fields_part3 + transect_fields_part4
transPt_fields = ['Dist_Seg', 'Dist_MHWbay', 'seg_x', 'seg_y',
    'DistSegDH', 'DistSegDL', 'DistSegArm',
    'SplitSort', 'ptZ', 'ptSlp', 'ptZmhw',
    'MAX_ptZmhw', 'MEAN_ptZmhw']

"""
# Update fieldnames to new:
transect_fields_v1 = ['SL_Lat', 'SL_Lon', 'SL_easting', 'SL_northing', 'Bslope',
    'DL_Lat', 'DL_Lon', 'DL_easting', 'DL_northing', 'DL_z', 'DL_zMHW',
    'DH_Lat', 'DH_Lon', 'DH_easting', 'DH_northing', 'DH_z', 'DH_zMHW',
    'Arm_Lat', 'Arm_Lon', 'Arm_easting', 'Arm_northing', 'Arm_z', 'Arm_zMHW',
    'DistDH', 'DistDL', 'DistArm']
old_fields = ['SL_x', 'SL_y', 'DL_x', 'DL_y', 'DL_z', 'DH_x', 'DH_y', 'DH_z', 'Arm_x', 'Arm_y', 'Arm_z']
arcpy.DeleteField_management(extendedTransects, old_fields)
for i in range(len(transect_fields_v1)):
    origfname = transect_fields_v1[i]
    newfname = transect_fields_part1[i]
    if newfname in old_fields:
        print("{} -> {}".format(origfname, newfname))
        arcpy.AlterField_management(extendedTransects, origfname, newfname)

transect_fields_v2 = ['MLW_easting','MLW_northing',
  'beach_h_MHW','beachWidth_MHW',
  'beach_h_MLW','beachWidth_MLW',
  'CP_easting','CP_northing','CP_zMHW']

arcpy.AddField_management(extendedTransects, 'DL_z', 'DOUBLE')
with arcpy.da.UpdateCursor(extendedTransects, ['DL_z', 'DL_zMHW']) as cursor:
    for row in cursor:
        try:
            row[0] = row[1] - dMHW
            cursor.updateRow(row)
        except TypeError:
            pass
arcpy.AddField_management(extendedTransects, 'DH_z', 'DOUBLE')
with arcpy.da.UpdateCursor(extendedTransects, ['DH_z', 'DH_zMHW']) as cursor:
    for row in cursor:
        try:
            row[0] = row[1] - dMHW
            cursor.updateRow(row)
        except TypeError:
            pass
arcpy.AddField_management(extendedTransects, 'Arm_z', 'DOUBLE')
with arcpy.da.UpdateCursor(extendedTransects, ['Arm_z', 'Arm_zMHW']) as cursor:
    for row in cursor:
        try:
            row[0] = row[1] - dMHW
            cursor.updateRow(row)
        except TypeError:
            pass
"""
