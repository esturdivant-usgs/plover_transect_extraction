# Use Forsythe_Development to create Forsythe2012_armor
# I expect that this will added to TE_preprocessing

import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension


SiteYear_strings = {'site': 'Forsythe',
                    'year': '2012',
                    'region': 'NewJersey',
                    'MHW':0.43,
                    'MLW':-0.61}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)

armorLines = '{site}{year}_armor'.format(**SiteYear_strings)
dev_poly = '{site}{year}_Development'.format(**SiteYear_strings)

arcpy.PolygonToLine_management(dev_poly, armorLines)
