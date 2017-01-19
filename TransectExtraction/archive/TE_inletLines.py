"""
"""

import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *




site = 'Cedar'
year = '2014'

arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\Virginia\{}\{}\{}{}.gdb'.format(site,year,site,year)

barrierBoundary = '{}{}_bndpoly'.format(site,year)

extendedTransects = site+"_extTrans_2014" # Created MANUALLY: see TransExtv4Notes.txt
rawtransects = False
rawbarrierline = 'LI_BND_2012Line'

