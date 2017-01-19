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


# arcpy.GetParameterAsText(0)
######## Set environments ################################################################
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
# mxd = arcpy.mapping.MapDocument("CURRENT")
# df = arcpy.mapping.ListDataFrames(mxd)[0]
#arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx") 				# Add XTools Pro toolbox
#arcpy.env.workspace=home= r'D:\ben_usgs\stippaData\FireIsland2012\FireIsland2012.gdb'
############ Inputs #########################
SiteYear_strings = {'site': 'Monomoy',
                    'year': '2014',
                    'region': 'Massachusetts',
                    'MHW':0.39,
                    'MLW':-0.95,
                    'MTL':-0.04}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(
    **SiteYear_strings)
out_dir = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\Extracted_Data'.format(**SiteYear_strings)

deletePtsWithZfill = False          # If True, dune points with elevations of fill (-99999) will be deleted
CreateMHWline = False
rawtransects = False
rawbarrierline = 'LI_BND_2012Line'
transUIDfieldname = "trans_sort"

########### Default Values ##########################
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

########### Automatic population ###########
site = SiteYear_strings['site']
MHW = SiteYear_strings['MHW']
MLW = SiteYear_strings['MLW']
dMHW = -MHW                    # Beach height adjustment
oMLW = MHW-MLW                      # MLW offset from MHW # Beach height adjustment (relative to MHW)
MTL = MHW-(MLW/2)
MTL = SiteYear_strings['MTL']
extendedTransects = "{site}{year}_extTrans".format(**SiteYear_strings) # Created MANUALLY: see TransExtv4Notes.txt
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
