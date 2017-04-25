'''
Prepare Fire Island 2014 data for use in TransectExtraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: emilysturdivant@gmail.com
Date last modified: 12/21/2015

Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
'''

import arcpy, time, os
from math import radians, cos, asin, sin, atan2, sqrt, degrees

arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\FireIsland_2012.gdb"

# Create single feature class for each set of points (shoreline, dune high, dune low)
SLdir = '\\Mac\Home\DATA\FireIsland2014\FIISshores2014'
DHdir = '\\Mac\Home\DATA\FireIsland2014\FIIS_dhighs2014'
DLdir = '\\Mac\Home\DATA\FireIsland2014\FIIS_dlows2014'

arcpy.env.workspace = SLdir
outfile = r"{}\{}".format(site_gdb,fname)
arcpy.Merge_management(arcpy.ListFiles('*.shp'),outfile)