"""

"""

import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

# INPUTS
site = 'Assawoman'
year = '2012'
old_dem = r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\lidar\AssawomanIsland_USGS_lidar_2012.tif'.format(site,year)
arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)

# OUTPUTS
new_dem = '{}{}_DEM'.format(site,year)
dem_5m = new_dem+'_5m'
proj_code = 26918

# PROCESSING
arcpy.ProjectRaster_management(old_dem,new_dem,arcpy.SpatialReference(proj_code),cell_size="1")
outAggreg = arcpy.sa.Aggregate(new_dem,5,'MEAN')
outAggreg.save(dem_5m)

