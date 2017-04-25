'''
Creation of boundary polygon for Deep Dive Transect Extraction
Requires: python 2.7, Arcpy
Author: Emily Sturdivant
email: emilysturdivant@gmail.com
Date last modified: 12/21/2015

Spatial reference used is NAD 83 UTM 18N: arcpy.SpatialReference(26918)
'''

"""
Modify shoreline polygon/line to different oceanside line
Variables:
    strings of existing files:
        homedir
        rawbarrierline
        MHW_oceanside
"""

import arcpy, time, os
from math import radians, cos, asin, sin, atan2, sqrt, degrees

arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension
arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\FireIsland_2012.gdb"

# Inputs
rawbarrierline = 'LI_BND_2012Line'
barrierBoundary = 'LongIsland_BND2012' 	# Barrier Boundary polygon
MHW_oceanside = 'FireIsland_MHWline_2012v2'

# Option 1:
if arcpy.Exists(barrierBoundary) == 0:
    arcpy.FeatureToPolygon_management(rawbarrierline,barrierBoundary)

arcpy.Densify_edit(barrierBoundary,'DISTANCE','50 METERS')
arcpy.Densify_edit(MHW_oceanside,'DISTANCE','50 METERS')
arcpy.Snap_edit(barrierBoundary,[[MHW_oceanside,'VERTEX','80 METERS']]) # Takes a while

# Option 2: (includes Option 1)
barrierBoundary = NewBNDpoly(rawbarrierline, MHW_oceanside, barrierBoundary)

def NewBNDpoly(boundary,newline,newboundary='boundary_poly'):
    # boundary = input line or polygon of boundary to be modified by newline
    desc = arcpy.Describe(boundary)
    type = desc.shapeType
    if type == "Line":
        arcpy.FeatureToPolygon_management(boundary,newboundary,'1 METER')
        boundary = newboundary
    arcpy.Densify_edit(boundary,'DISTANCE','50 METERS')
    arcpy.Densify_edit(newline,'DISTANCE','50 METERS')
    arcpy.Snap_edit(boundary,[[newline,'VERTEX','100 METERS']]) # Takes a while
    return boundary # string name of new polygon