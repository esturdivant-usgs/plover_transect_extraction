'''
Deep dive Transect Extraction for Fire Island, NY 2012
Requires: python 2.7, Arcpy
Author: Sawyer Stippa, modified by Ben Gutierrez & Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 2/26/2016

Notes:
    Run in ArcMap python window;
    Turn off "auto display" in ArcMap preferences, In Geoprocessing Options, uncheck display results of geoprocessing...
    Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
    see TransExtv4Notes.txt for more

'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

############ Inputs #########################
SYvars = {'site': 'Cedar',
                    'year': '2014',
                    'region': 'Delmarva',
                    'code': 'cei14',
                    'MHW': .34,
                    'MLW': -0.9,
                    'MTL': None}
SYvars['home'] = r"\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive"\
                           r"\{region}\{site}\{year}\{site}{year}.gdb".format(**SYvars)

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 						# Overwrite output?
arcpy.CheckOutExtension("Spatial") 						# Checkout Spatial Analysis extension

############## Inputs ###############################
arcpy.env.workspace = home = SYvars['home']
archive_dir=r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive'\
            r'\{region}\{site}\All_Years\{site}_transects.gdb'.format(**SYvars)
out_dir=r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive'\
        r'\{region}\{site}\{year}\Extracted_Data'.format(**SYvars)

############## Site-level Inputs ###############################
orig_extTrans = os.path.join(archive_dir, '{site}_extTrans'.format(**SYvars))
orig_tidytrans = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SYvars))
rst_transID = os.path.join(archive_dir, '{site}_rstTransID'.format(**SYvars))

############## Year-specific Inputs ###############################
#extendedTrans = "{site}_extTrans".format(**SYvars) # Created MANUALLY: see TransExtv4Notes.txt
ShorelinePts = '{site}{year}_shoreline'.format(**SYvars)
dhPts = 'BP{year}_DHpts'.format(**SYvars)				# Dune crest
dlPts = 'BP{year}_DLpts'.format(**SYvars) 		  # Dune toe
inletLines = 'BP_inletLines' #.format(**SYvars)  # manually created
armorLines = 'BP_armorshoreward_{year}'.format(**SYvars)
barrierBoundary = 'BP_boundarypoly_{year}_edit1'.format(**SYvars) # Barrier Boundary polygon
shoreline = 'BP{year}_ShoreBetweenInlets'.format(**SYvars)    # Complete shoreline ready to become route in Pt. 2
elevGrid = 'BP_DEM_{year}'.format(**SYvars)				# Elevation
elevGrid_5m = elevGrid+'_5m'				# Elevation
#habitat = 'habitat_201211' 			# Habitat
slopeGrid = 'BP{year}_slope5m'.format(**SYvars)

############## Outputs ###############################
extendedTransects = '{site}{year}_extTrans_working'.format(**SYvars)
# dh2trans = '{site}{year}_DH2trans'.format(**SYvars)							# DHigh within 10m
# dl2trans = '{site}{year}_DL2trans'.format(**SYvars)						# DLow within 10m
# arm2trans = '{site}{year}_arm2trans'.format(**SYvars)
# oceanside_auto = '{site}{year}_MHWfromSLPs'.format(**SYvars)
# shl2trans = '{site}{year}_SHL2trans'.format(**SYvars)							# beach slope from lidar within 10m of transect
MLWpts = '{site}{year}_MLW2trans'.format(**SYvars)                     # MLW points calculated during Beach Width calculation
CPpts = '{site}{year}_topBeachEdgePts'.format(**SYvars)                     # Points used as upper beach edge for Beach Width and height


extTrans_tidy = "{site}{year}_tidyTrans".format(**SYvars)
# transects_part2 = os.path.join(home,'trans_part2')
# transects_final = '{site}{year}_trans_populated'.format(**SYvars)
transPts = '{site}{year}_transPts_working'.format(**SYvars) 	# Outputs Transect Segment points
transPts_null = '{site}{year}_transPts_null'.format(**SYvars)
transPts_fill= '{site}{year}_transPts_fill'.format(**SYvars)
transPts_shp = '{site}{year}_transPts_shp'.format(**SYvars)
# transPts_bw = '{site}{year}_transPts_beachWidth_fill'.format(**SYvars)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')
out_stats = os.path.join(home,"avgZ_byTransect")
#extTrans_tidy_archive = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SYvars))
#beachwidth_rst = "{site}{year}_beachWidth".format(**SYvars)

transPts_presort = 'transPts_presort'

rst_transPopulated = "{site}{year}_rstTrans_populated".format(**SYvars)
rst_trans_grid = "{code}_trans".format(**SYvars)

########### Automatic population ###########
MHW = SYvars['MHW']
MLW = SYvars['MLW']
dMHW = -MHW                         # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
SYvars['MTL'] = MTL = (MHW+MLW)/2

########### Default Values ##########################
transUIDfield = "sort_ID"
fill = 9999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
if SYvars['site'] == 'Monomoy':
    maxDH = 3
else:
    maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
extendlength = 3000                      # extended transects distance (m) IF NEEDED
if SYvars['region'] == 'Massachusetts' or SYvars['region'] == 'RhodeIsland' or SYvars['region'] == 'Maine':
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
