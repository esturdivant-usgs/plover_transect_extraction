'''
Configuration file for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 11/22/2016
'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

############ Inputs #########################
SiteYear_strings = {'site': 'FireIsland',
                    'year': '2012',
                    'region': 'NewYork',
                    'code': 'fi12',
                    'MHW': .46,
                    'MLW': -1.01,
                    'MTL': None}
SiteYear_strings['home'] = r"\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb".format(**SiteYear_strings)

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 						# Overwrite output?
arcpy.CheckOutExtension("Spatial") 						# Checkout Spatial Analysis extension

CreateMHWline = False
rawtransects = False

############## Inputs ###############################
arcpy.env.workspace = home = SiteYear_strings['home']
#arcpy.env.workspace = home = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format( **SiteYear_strings)
archive_dir=r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\All_Years\{site}_transects.gdb'.format(**SiteYear_strings)
out_dir=r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)

############## Inputs ###############################
orig_extTrans = os.path.join(archive_dir, '{site}_extTrans'.format(**SiteYear_strings))
orig_tidytrans = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SiteYear_strings))
rst_transID = os.path.join(archive_dir, '{site}_rstTransID'.format(**SiteYear_strings))
extTrans_tidy_archive = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SiteYear_strings))

extendedTrans = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt
ShorelinePts = 'FI{year}_SLpts'.format(**SiteYear_strings)
dhPts = 'FI{year}_DHpts'.format(**SiteYear_strings)				# Dune crest
dlPts = 'FI{year}_DLpts'.format(**SiteYear_strings) 		  # Dune toe
inletLines = 'FI{year}_inletLines'.format(**SiteYear_strings)  # manually created
armorLines = 'FI{year}_nonfencingstructures'.format(**SiteYear_strings)
barrierBoundary = '{site}{year}_FullShoreline'.format(**SiteYear_strings)   # Barrier Boundary polygon
elevGrid = '{site}{year}_DEM'.format(**SiteYear_strings)				# Elevation
elevGrid_5m = elevGrid+'_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat

############## Outputs ###############################
extendedTransects = '{site}{year}_extTrans_working'.format(**SiteYear_strings)
MLWpts = '{site}{year}_MLW2trans'.format(**SiteYear_strings)                     # MLW points calculated during Beach Width calculation
CPpts = '{site}{year}_topBeachEdgePts'.format(**SiteYear_strings)                     # Points used as upper beach edge for Beach Width and height
shoreline = '{site}{year}_ShoreBetweenInlets'.format(**SiteYear_strings)        # Complete shoreline ready to become route in Pt. 2
slopeGrid = '{site}{year}_slope_5m'.format(**SiteYear_strings)

extTrans_tidy = "{site}{year}_tidyTrans".format(**SiteYear_strings)
transPts = '{site}{year}_transPts_working'.format(**SiteYear_strings) 	# Outputs Transect Segment points
transPts_null = '{site}{year}_transPts_null'.format(**SiteYear_strings)
transPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)
transPts_shp = '{site}{year}_transPts_shp'.format(**SiteYear_strings)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')
out_stats = os.path.join(home,"avgZ_byTransect")

transPts_presort = 'transPts_presort'

rst_transID = "{site}{year}_rstTransID".format(**SiteYear_strings)
rst_transPopulated = "{site}{year}_rstTrans_populated".format(**SiteYear_strings)
rst_trans_grid = "{code}_trans".format(**SiteYear_strings)

########### Automatic population ###########
MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
dMHW = -MHW                         # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
SiteYear_strings['MTL'] = MTL = (MHW+MLW)/2

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
