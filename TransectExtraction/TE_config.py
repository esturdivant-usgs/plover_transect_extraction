'''
Configuration file for Deep dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: esturdivant@usgs.gov; bgutierrez@usgs.gov; sawyer.stippa@gmail.com
Date last modified: 11/22/2016
'''
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
#sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
# mxd = arcpy.mapping.MapDocument("CURRENT")
# df = arcpy.mapping.ListDataFrames(mxd)[0]
#arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'

############ Inputs #########################
SiteYear_strings = {'site': 'ParkerRiver',
                    'year': '2014',
                    'region': 'Massachusetts',
                    'MHW':1.22,
                    'MLW':-1.37, # average of approximate MLW on Chesapeake Bay side (-0.47) and Atlantic side (-0.58)
                    'MTL':None}

CreateMHWline = False
rawtransects = False
#rawbarrierline = 'LI_BND_2012Line'
plover_rst_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\Zeigler_analysis\Layers_for_BN\{year}\BaseLayers'.format(
    **SiteYear_strings)
arcpy.env.workspace = plover_rst_dir
cellsize_rst = arcpy.ListRasters()[0]

########### Automatic population ###########
arcpy.env.workspace = home = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(
    **SiteYear_strings)
SiteYear_strings['home'] = home
out_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)
archive_dir = r'\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\{region}\{site}\All_Years\{site}_transects.gdb'.format(**SiteYear_strings)

MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
dMHW = -MHW                    # Beach height adjustment
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

extTrans_tidy = "{site}{year}_tidytrans".format(**SiteYear_strings)
transects_part2 = os.path.join(home,'trans_part2')
transects_final = '{site}{year}_trans_populated'.format(**SiteYear_strings)
trans_clipped = 'trans_clipped2island'
tranSplitPts = '{site}{year}_transPts_working'.format(**SiteYear_strings) 	# Outputs Transect Segment points
tranSplitPts_null = '{site}{year}_transPts_null'.format(**SiteYear_strings)
tranSplitPts_fill= '{site}{year}_transPts_fill'.format(**SiteYear_strings)
tranSplitPts_shp = '{site}{year}_transPts_shp'.format(**SiteYear_strings)
tranSplitPts_bw = '{site}{year}_transPts_beachWidth_fill'.format(**SiteYear_strings)
pts_elevslope = os.path.join(home,'transPts_ZmhwSlp')
extTrans_tidy_archive = os.path.join(archive_dir, '{site}_tidyTrans'.format(**SiteYear_strings))
beachwidth_rst = "{site}{year}_beachWidth".format(**SiteYear_strings))

########### Default Values ##########################
transUIDfield = "sort_ID"
fill = -99999	  					# Replace Nulls with
pt2trans_disttolerance = "25 METERS"        # Maximum distance that point can be from transect and still be joined; originally 10 m
if SiteYear_strings['site'] == 'Monomoy':
    maxDH = 3
else:
    maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
extendlength = 3000                      # extended transects distance (m) IF NEEDED
if SiteYear_strings['region'] == 'Massachusetts' or SiteYear_strings['region'] == 'RhodeIsland' or SiteYear_strings['region'] == 'Maine':
    proj_code = 26919 # "NAD 1983 UTM Zone 19N"
    utmSR = arcpy.SpatialReference(proj_code)
else:
    proj_code = 26918 # "NAD 1983 UTM Zone 18N"
    utmSR = arcpy.SpatialReference(proj_code)
