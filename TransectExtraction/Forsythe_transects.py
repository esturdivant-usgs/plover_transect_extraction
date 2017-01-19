# process Forsythe extTransects 
import arcpy, time, os, pythonaddins, sys, math
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *
arcpy.env.overwriteOutput = True 											# Overwrite output?
arcpy.CheckOutExtension("Spatial") 											# Checkout Spatial Analysis extension

# INPUTS - same as TE
SiteYear_strings = {'site': 'Forsythe',
                    'year': '2014',
                    'region': 'NewJersey'}
arcpy.env.workspace = home = r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)

# INPUTS - not in TE
fill = -99999
old_transects = '{region}N_LT'.format(**SiteYear_strings)
extTransects = 'Forsythe_extTrans'
new_extTrans = 'Forsythe_extTrans_v2'
in_file = extTransects

"""
PROCESSING
"""
# Loops through each of the fields, 
# creates a FieldMap object that retrieves the old value for each field, 
# and adds the FieldMap to the FieldMappings
fieldlist = arcpy.ListFields(extTransects)[2:18]
for i in range(len(fieldlist)):
	fieldlist[i] = fieldlist[i].name
fms = arcpy.FieldMappings()
for field in fieldlist:
	print field.name
	fm = arcpy.FieldMap()
	fm.addInputField(old_transects, field)
	fms.addFieldMap(fm)
arcpy.SpatialJoin_analysis(extTransects, old_transects, new_extTrans, 'JOIN_ONE_TO_ONE', 
	join_type='KEEP_ALL', field_mapping=fms, match_option='WITHIN_A_DISTANCE',search_radius='5 METERS')

# Replace false attributes with None values 
# Select features that did not have spatial match in old_transects
arcpy.SelectLayerByAttribute_management(new_extTrans,"ADD_TO_SELECTION","Join_Count=0")
# Overwrite values with fill in selected features
for field in fieldlist:
	arcpy.CalculateField_management(new_extTrans, field, fill)
# Replace fills with Null values
ReplaceValueInFC(new_extTrans,fields=[],oldvalue=-99999,newvalue=None)
# delete fields used in processing
arcpy.DeleteField_management(new_extTrans, ['Join_Count','TARGET_FID'])

# Transect processing
in_fc = 'Forsythe_extTrans_v2'
base_fc = 'Forsythe_extTrans_v3'
sortfield = 'trans_sort'
sort_corner='LL'

arcpy.CreateFeatureclass_management(home,'sort_line1', "POLYLINE", projCR)
arcpy.CopyFeatures_management('sort_line1','{}\\sort_line2'.format(home))
sort_line_list = ['sort_line1','sort_line2']

SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield='trans_sort',sort_corner='LL')


"""
# Completely refused to work. Perhaps because there were some fields that did not accept None value (ProcTime and Autogen)
blank_row = [fill]*len(fieldlist)
with arcpy.UpdateCursor(new_extTrans, where_clause="Join_Count = 0", fields=fieldlist) as cursor:
	for row in cursor:
		#row[:] = None
		#cursor.updateRow(row)
		cursor.updateRow(blank_row)
"""

# Delete fields from extTransects

# Join values based on 


"""
Experiment to generate shoreline (ShoreBetweenInlets) from full_shoreline
"""
def CreateShoreBetweenInlets(shore_delineator,inletLines,out_line,shoreline_pts, proj_code=26918):
    # Ready layers for processing
    DeleteExtraFields(inletLines)
    DeleteExtraFields(shore_delineator)
    if not arcpy.Describe(shore_delineator).spatialReference.factoryCode == proj_code:
        shore_delineator = ReProject(shore_delineator,shore_delineator+'_utm',proj_code)
    typeFC = arcpy.Describe(shore_delineator).shapeType
	if typeFC == "Point" or typeFC =='Multipoint':
        # Create shoreline from shoreline points
        arcpy.PointsToLine_management(shore_delineator, 'line_temp')
        shore_delineator = 'shore_temp'
        # Merge and then extend shoreline to inlet lines
        arcpy.Merge_management(['line_temp',inletLines],shore_delineator)
        arcpy.ExtendLine_edit(shore_delineator,'500 Meters')
    # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
    arcpy.FeatureToLine_management([shore_delineator, inletLines], 'split_temp')
    # alternative (more efficient?):
 	# arcpy.SelectLayerByLocation_management('split_temp', "INTERSECT", ShorelinePts, '1 METERS', invert_spatial_relationship="INVERT")
	# arcpy.DeleteFeatures_management('split_temp')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", shoreline_pts,'1 METERS')
    # count intersecting inlet lines
    arcpy.SpatialJoin_analysis('split_temp',inletLines,out_line,"JOIN_ONE_TO_ONE")
    ReplaceFields(shoreline_pts,{'ORIG_FID':'OID@'},'SHORT')
    return out_line




