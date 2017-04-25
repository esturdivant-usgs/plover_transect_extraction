

import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *


arcpy.SpatialJoin_analysis(tranSplitPts,pts_elevslope,tranSplitPts+'_redojoin',)


"""
Calculate beach height for FI2014
"""
arcpy.env.workspace=home= r"\\Mac\Home\Documents\ArcGIS\TE_NewYork\FireIsland2014.gdb"

year = '2014'
site = 'FI'

# Site-specific values
MLW = -1.01 						# MLW offset from MHW # Beach height adjustment (relative to MHW)
dMHW = -.46

MLWpts = site+year+'_MLW2trans'
fill = -99999  # Replace Nulls with
pt2trans_disttolerance = "25 METERS"  # Maximum distance that point can be from transect and still be joined; originally 10 m
maxDH = 2.5
nad83 = arcpy.SpatialReference(4269)
nad83utm18 = arcpy.SpatialReference(26918)
extendlength = 2000
baseName = 'trans_clip_working'                     # Clipped transects
transects_part2 = site+year+'_transpart2'
transects_final = site+year+'_populatedTransects'
tranSplitPts = site+year+'_trans_5mPts_working' 	# Outputs Transect Segment points
transSplitPts_final = site+year+'_trans_5mPts'
pts_elevslope = tranSplitPts+'_ZSlp'

# Calculate additional beach parameters
# Set fields that will be used to calculate beach width and store the results
fields = ['DL_z','DH_z','Arm_z',
          'DL_easting','DL_northing',
          'DH_easting','DH_northing',
          'Arm_easting','Arm_northing',
          'Bslope',
          'DistDH','DistDL','DistArm',
          'SL_easting',
          'SL_northing',
          'MLW_easting',
          'MLW_northing',
          'beach_h_MLW',
          'beachWidth_MLW',
          'Source_beachwidth']
distfields = ['DistDH','DistDL','DistArm']

# Add fields if don't already exist
if not fieldExists(baseName, 'Source_beachwidth'):
    arcpy.AddField_management(baseName, 'Source_beachwidth', "TEXT",3)
    print 'Added Source_beachwidth field to '+baseName
for newfname in fields:
    if not fieldExists(baseName, newfname):
        arcpy.AddField_management(baseName, newfname, "DOUBLE")
        print 'Added '+newfname+' field to '+baseName

# Calculate
errorct = 0
transectct = 0
with arcpy.da.UpdateCursor(baseName,'*') as cursor:
    for row in cursor:
        transectct +=1
        # Find which of DL, DH, and Arm is closest to SL and not Null
        cp = FindNearestPointWithZvalue(row,cursor.fields,distfields,maxDH) # prefix of closest point metric
        if cp:
            # Set values from each row
            d_x = row[cursor.fields.index(cp+'_easting')]
            d_y = row[cursor.fields.index(cp+'_northing')]
            b_slope = row[cursor.fields.index('Bslope')]
            sl_x = row[cursor.fields.index('SL_easting')]
            sl_y = row[cursor.fields.index('SL_northing')]
            d_z = row[cursor.fields.index(cp+'_zMHW')]

            # Calculate beach height
            beach_h_MLW = d_z-MLW
            # Calculate beach width
            mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_v2(MLW,d_x,d_y,b_slope,sl_x,sl_y)

            # update Row values
            row[cursor.fields.index('MLW_easting')] = mlw_x
            row[cursor.fields.index('MLW_northing')] = mlw_y
            row[cursor.fields.index('beach_h_MLW')] = beach_h_MLW
            row[cursor.fields.index('beachWidth_MLW')] = beachWidth_MLW
            row[cursor.fields.index('Source_beachWidth')] = cp
            cursor.updateRow(row)
        else:
            errorct +=1
            pass
# Report
print "Beach Width could not be calculated for {} out of {} transects.".format(errorct,transectct)

# Create MLW points for error checking
arcpy.MakeXYEventLayer_management(baseName,'MLW_easting','MLW_northing',MLWpts+'_lyr',nad83utm18)
arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)

arcpy.CopyFeatures_management(baseName,transects_final)
#ReplaceValueInFC(transects_final,[],None,fill) # Replace null values with -99999 for final transects file, before segmenting

print "Creation of " + transects_final + " completed. "
#print "Creation of " + transects_final + " completed. Proceeding to create 5m segments and points."











fill = -99999

arcpy.env.workspace= r"\\Mac\Home\Documents\ArcGIS\BreezyPt2010_v2.gdb"
tranSplitPts = 'BP2010_trans_5mPts_working'
elevGrid_5m = u'BP_DEM_2010_5m'
slopeGrid = 'BP_slope5m_2010'
pts_elevslope = 'BP2010_trans_5mPts_working_ZSlp'
transSplitPts_table = 'BP2010_trans_5mPts_table'
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,[[elevGrid_5m,'PointZ'],[slopeGrid,'PointSlp']])
arcpy.CopyFeatures_management(pts_elevslope, tranSplitPts)
arcpy.MakeTableView_management(tranSplitPts,transSplitPts_table)
ReplaceValueInFC(transSplitPts_table,[], None, fill)


arcpy.env.workspace= r"\\Mac\Home\Documents\ArcGIS\BreezyPt2012_v2.gdb"
tranSplitPts = 'BP2012_trans_5mPts_working'
elevGrid_5m = 'BreezyPoint_USACE2012_DEM'
slopeGrid = 'BP_slope5m_2012'
pts_elevslope = 'BP2012_trans_5mPts_working_ZSlp'
transSplitPts_table = 'BP2012_trans_5mPts_table'
arcpy.sa.ExtractMultiValuesToPoints(tranSplitPts,[[elevGrid_5m,'PointZ'],[slopeGrid,'PointSlp']])
arcpy.CopyFeatures_management(tranSplitPts,pts_elevslope)
arcpy.MakeTableView_management(tranSplitPts,transSplitPts_table)
ReplaceValueInFC(transSplitPts_table,[], None, fill)

