# -*- coding: utf-8 -*-

# Transect Extraction module
# possible categories: preprocess, create, calculate

import arcpy
import time
import os
import pythonaddins
import collections
import pandas as pd
import numpy as np
from operator import add
import sys
if sys.platform == 'win32':
    script_path = r"\\Mac\Home\GitHub\plover_transect_extraction\TransectExtraction"
    sys.path.append(script_path) # path to TransectExtraction module
    import arcpy
    import pythonaddins
    from TE_functions_arcpy import *
if sys.platform == 'darwin':
    script_path = '/Users/esturdivant/GitHub/plover_transect_extraction/TransectExtraction'
    sys.path.append(script_path)
from TE_functions import *

# General use functions
def SetInputFCname(workingdir, varname, inFCname, system_ext=True):
    if arcpy.Exists(inFCname):
        inFCname = inFCname
    else:
        try:
            FCname = pythonaddins.OpenDialog("Select "+varname+" File (e.g. "+inFCname+")", False, workingdir,'Select')
        except RuntimeError:
            FCname = raw_input("{} File (e.g. {} or '0' for none): ".format(varname, inFCname))
            if FCname == '0':
                FCname = False
            elif not arcpy.Exists(FCname):
                FCname = raw_input("{} doesn't exist. Try again. \n{} File (e.g. {}): ".format(FCname, varname, inFCname))
        if FCname:
            inFCname = os.path.basename(FCname)
        else:
            print 'No data selected for {}.'.format(inFCname)
            inFCname = False
            if system_ext:
                raise SystemExit
    return inFCname

def unique_values(table, field):
    # return sorted unique values in field
    data = arcpy.da.TableToNumPyArray(table, [field])
    return numpy.unique(data[field])

# Check for anomalous values in FC:
def CheckValues(inFeatureClass,fieldName,expectedRange):
    lowrows = list()
    highrows = list()
    expectedRange.sort() # make sure pair is [low,high]
    with arcpy.da.UpdateCursor(inFeatureClass,[fieldName,'trans_sort']) as cursor:
        for row in cursor:
            if row[0]< expectedRange[0]:
                row[0] = None
                lowrows.append(row[1])
            elif row[0]>expectedRange[1]:
                row[0] = None
                highrows.append(row[1])
            else:
                pass
            cursor.updateRow(row)
    return lowrows,highrows

def fieldsAbsent(in_fc, fieldnames):
    try:
        fieldList = arcpy.ListFields(os.path.join(arcpy.env.workspace,in_fc))
    except:
        fieldList = arcpy.ListFields(in_fc)
    fnamelist = [f.name.lower() for f in fieldList]
    mfields = []
    for fn in fieldnames:
        if not fn.lower() in fnamelist:
            mfields.append(fn)
    if not len(mfields):
        print("All expected fields present in file '{}'.".format(in_fc))
        return False
    else:
        print("Fields '{}' not present in transects file '{}'.".format(
              mfields, in_fc))
        return mfields

def fieldExists(in_fc, fieldname):
    try:
        fieldList = arcpy.ListFields(os.path.join(arcpy.env.workspace, in_fc))
    except:
        fieldList = arcpy.ListFields(in_fc)
    for f in fieldList:
        if f.name.lower() == fieldname.lower():
            return True
    return False

def CopyAndWipeFC(in_fc, out_fc, preserveflds=[]):
    # Make copy of transects and manually fill the gaps. Then select all the new transect and run the next piece of code.
    arcpy.CopyFeatures_management(in_fc, out_fc)
    # Replace values of all new transects
    fldsToWipe = [f.name for f in arcpy.ListFields(out_fc)
                  if not f.required and not f.name in preserveflds] # list all fields that are not required in the FC (e.g. OID@)
    with arcpy.da.UpdateCursor(out_fc, fldsToWipe) as cursor:
        for row in cursor:
            cursor.updateRow([None] * len(row))
    return out_fc

def AddNewFields(fc,fieldlist,fieldtype="DOUBLE", verbose=True):
    # Add fields to FC if they do not already exist. New fields must all be the same type.
    # print('Adding fields to {} as type {} if they do not already exist.'.format(out_fc, fieldtype))
    def AddNewField(fc, newfname, fieldtype, verbose):
        # Add single new field
        if not fieldExists(fc, newfname):
            arcpy.AddField_management(fc, newfname, fieldtype)
            if verbose:
                print('Added {} field to {}'.format(newfname, fc))
        return fc
    # Execute for multiple fields
    if type(fieldlist) is str:
        AddNewField(fc, fieldlist, fieldtype, verbose)
    elif type(fieldlist) is list or type(fieldlist) is tuple:
        for newfname in fieldlist:
            AddNewField(fc, newfname, fieldtype, verbose)
    else:
        print("fieldlist accepts string, list, or tuple of field names. {} type not accepted.".format(type(fieldlist)))
    return fc

def DeleteExtraFields(inTable, keepfields=[]):
    fldsToDelete = [x.name for x in arcpy.ListFields(inTable) if not x.required] # list all fields that are not required in the FC (e.g. OID@)
    if keepfields:
        [fldsToDelete.remove(f) for f in keepfields if f in fldsToDelete] # remove keepfields from fldsToDelete
    if len(fldsToDelete):
        arcpy.DeleteField_management(inTable, fldsToDelete)
    return inTable

def DeleteTempFiles(wildcard='*_temp'):
    # Delete files of type FC, Dataset, or Table ending in '_temp' fromw workspace
    templist = []
    try:
        templist = templist + arcpy.ListFeatureClasses(wildcard)
    except:
        pass
    try:
        templist = templist + arcpy.ListDatasets(wildcard)
    except:
        pass
    try:
        templist = templist + arcpy.ListTables(wildcard)
    except:
        pass
    for tempfile in templist:
        arcpy.Delete_management(tempfile)
    return templist

def RemoveLayerFromMXD(lyrname):
    # accepts wildcards
    try:
        mxd = arcpy.mapping.MapDocument('CURRENT')
        for df in arcpy.mapping.ListDataFrames(mxd):
            for lyr in arcpy.mapping.ListLayers(mxd, lyrname, df):
                arcpy.mapping.RemoveLayer(df, lyr)
                return True
            else:
                return True
    except:
        print("Layer '{}' could not be removed from map document.".format(lyrname))
        return False

def newcoord(coords, dist):
    # From: gis.stackexchange.com/questions/71645/extending-line-by-specified-distance-in-arcgis-for-desktop
    # Computes new coordinates x3,y3 at a specified distance along the
    # prolongation of the line from x1,y1 to x2,y2
    (x1,y1),(x2,y2) = coords
    dx = x2 - x1 # change in x
    dy = y2 - y1 # change in y
    linelen =np.hypot(dx, dy) # distance between xy1 and xy2
    x3 = x2 + dx/linelen * dist
    y3 = y2 + dy/linelen * dist
    return x3, y3

def ReplaceFields(fc, newoldfields, fieldtype='DOUBLE'):
    # Use tokens to save geometry properties as attributes
    # E.g. newoldfields={'LENGTH':'SHAPE@LENGTH'}
    spatial_ref = arcpy.Describe(fc).spatialReference
    for (new, old) in newoldfields.items():
        if not fieldExists(fc, new): # Add field if it doesn't already exist
            arcpy.DeleteField_management(fc, new)
            arcpy.AddField_management(fc, new, fieldtype)
        with arcpy.da.UpdateCursor(fc, [new, old], spatial_reference=spatial_ref) as cursor:
            for row in cursor:
                cursor.updateRow([row[1], row[1]])
        if fieldExists(fc, old):
            try:
                arcpy.DeleteField_management(fc,old)
            except:
                print(arcpy.GetMessage(2))
                pass
    return fc

def DuplicateField(fc, fld, newname, ftype=False):
    # Copy field values into field with new name
    # 1. get field type
    if not ftype:
        flds = arcpy.ListFields(fc, fld)
        ftype = flds.type
    # 2. add new field
    arcpy.AddField_management(fc, newname, ftype)
    # 3. copy values
    with arcpy.da.UpdateCursor(fc, [fld, newname]) as cursor:
        for row in cursor:
            cursor.updateRow([row[0], row[0]])
    return(fc)

def AddXYAttributes(fc, newfc, prefix, proj_code=26918):
    try:
        try:
            RemoveLayerFromMXD(fc)
        except:
            pass
        arcpy.MultipartToSinglepart_management(fc,newfc) # failed for SHL2trans_temp: says 'Cannot open...'
    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        print "Attempting to continue"
        #RemoveLayerFromMXD(fc)
        arcpy.FeatureClassToFeatureClass_conversion(fc,arcpy.env.workspace,newfc)
        pass
    fieldlist = [prefix+'_Lat',prefix+'_Lon',prefix+'_x',prefix+'_y']
    AddNewFields(newfc, fieldlist)
    with arcpy.da.UpdateCursor(newfc, [prefix+'_Lon', prefix+'_Lat',"SHAPE@XY"], spatial_reference=arcpy.SpatialReference(4269)) as cursor:
        [cursor.updateRow([row[2][0], row[2][1], row[2]]) for row in cursor]
    with arcpy.da.UpdateCursor(newfc,[prefix+'_x',prefix+'_y',"SHAPE@XY"], spatial_reference=arcpy.SpatialReference(proj_code)) as cursor:
        [cursor.updateRow([row[2][0], row[2][1], row[2]]) for row in cursor]
    return newfc, fieldlist

def ReplaceValueInFC(fc, oldvalue=-99999, newvalue=None, fields="*"):
    # Replace oldvalue with newvalue in fields in fc
    # First check field types
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        fieldindex = range(len(cursor.fields))
        for row in cursor:
            for i in fieldindex:
                if row[i] == oldvalue:
                    row[i] = newvalue
            cursor.updateRow(row)
                    # try:
                    #     row[i] = newvalue
                    #     cursor.updateRow(row)
                    # except RuntimeError:
                    #     print(cursor.fields[i])
                    #     #print(row)
    return fc

def ReProject(fc,newfc,proj_code=26918):
    if not arcpy.Describe(fc).spatialReference.factoryCode == proj_code: # NAD83 UTM18N
        arcpy.Project_management(fc,newfc,arcpy.SpatialReference(proj_code))
    else:
        newfc = fc
    return newfc

def DeleteFeaturesByValue(fc,fields=[], deletevalue=-99999):
    if not len(fields):
        fs = arcpy.ListFields(fc)
        for f in fs:
            fields.append(f.name)
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            for i in range(len(fields)):
                if row[i] == deletevalue:
                    cursor.deleteRow()
    return fc

# Part 1 functions
def ProcessDEM(elevGrid, elevGrid_5m, utmSR):
    # If cell size is not 1x1m in NAD83 UTM Zone__, Project it to such.
    # Aggregate the raster to 5m x 5m
    sr = arcpy.Describe(elevGrid).spatialReference
    cs = arcpy.GetRasterProperties_management(elevGrid, "CELLSIZEX")
    if sr != utmSR or cs.getOutput(0) != '1':
        elevGrid2 = elevGrid+'_projected'
        arcpy.ProjectRaster_management(elevGrid, elevGrid2, utmSR,cell_size="1")
    else:
        elevGrid2 = elevGrid
    outAggreg = arcpy.sa.Aggregate(elevGrid2,5,'MEAN')
    outAggreg.save(elevGrid_5m)
    return(elevGrid_5m)

def ExtendLine(fc, new_fc, distance, proj_code=26918):
    # From GIS stack exchange http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance
    # layer must have map projection
    def accumulate(iterable):
        # accumulate([1,2,3,4,5]) --> 1 3 6 10 15
        # (Equivalent to itertools.accumulate() - isn't in Python 2.7)
        it = iter(iterable)
        total = next(it) # initialize with the first value
        yield total
        for element in it:
            total = add(total, element)
            yield total
    # Project transects to UTM
    if not arcpy.Describe(fc).spatialReference.factoryCode == proj_code:
        print 'Projecting {} to UTM'.format(fc)
        arcpy.Project_management(fc, fc+'utm_temp', arcpy.SpatialReference(proj_code))  # project to PCS
        arcpy.FeatureClassToFeatureClass_conversion(fc+'utm_temp', arcpy.env.workspace, new_fc)
    else:
        print '{} is already projected in UTM.'.format(fc)
        arcpy.FeatureClassToFeatureClass_conversion(fc, arcpy.env.workspace, new_fc)
    #OID is needed to determine how to break up flat list of data by feature.
    coordinates = [[row[0], row[1]] for row in
                   arcpy.da.SearchCursor(fc, ["OID@", "SHAPE@XY"],
                   explode_to_points=True)]
    oid, vert = zip(*coordinates)
    # Construct list of numbers that mark the start of a new feature class by
    # counting OIDs and accumulating the values.
    vertcounts = list(accumulate(collections.Counter(oid).values()))
    # Grab the last two vertices of each feature
    lastpoint = [point for x,point in enumerate(vert) if x+1 in vertcounts or x+2 in vertcounts]
    # Obtain list of tuples of new end coordinates by converting flat list of
    # tuples to list of lists of tuples.
    newvert = [newcoord(y, float(distance)) for y in zip(*[iter(lastpoint)]*2)]
    j = 0
    with arcpy.da.UpdateCursor(new_fc, "SHAPE@XY", explode_to_points=True) as cursor:
        for i, row in enumerate(cursor):
            if i+1 in vertcounts:
                row[0] = newvert[j]
                j+=1
                cursor.updateRow(row) #FIXME: If the FC was projected as part of the function, returns RuntimeError: "The spatial index grid size is invalid."
    return new_fc

def PrepTransects_part2(trans_presort, LTextended, barrierBoundary='', trans_sort_1='trans_sort_temp', sort_corner="LR"):
    # 2. Remove orig transects from manually created transects # Delete any NAT transects in the new transects layer
    arcpy.SelectLayerByLocation_management(trans_presort, "ARE_IDENTICAL_TO",  # or "SHARE_A_LINE_SEGMENT_WITH"
                                           LTextended)
    if int(arcpy.GetCount_management(trans_presort)[0]):
        # if old trans in new trans, delete them
        arcpy.DeleteFeatures_management(trans_presort)
    # 3. Append relevant NAT transects to the new transects
    if len(barrierBoundary)>0:
        arcpy.SelectLayerByLocation_management(LTextended, "INTERSECT", barrierBoundary)
    arcpy.Append_management(LTextended, trans_presort)
    # trans_sort_1, count1 = SpatialSort(trans_presort, trans_sort_1, sort_corner,
    #                                    reverse_order=False, sortfield="sort_ID")
    return(trans_presort)

def SpatialSort(in_fc, out_fc, sort_corner='LL', reverse_order=False, startcount=0, sortfield='sort_ID'):
    # Sort transects and assign values to new sortfield; option to assign values in reverse order
    arcpy.Sort_management(in_fc,out_fc,[['Shape','ASCENDING']],sort_corner) # Sort from lower left - this
    try:
        arcpy.AddField_management(out_fc,sortfield,'SHORT')
    except:
        pass
    rowcount = int(arcpy.GetCount_management(out_fc)[0])
    if reverse_order:
        with arcpy.da.UpdateCursor(out_fc,['OID@',sortfield]) as cursor:
            for row in cursor:
                cursor.updateRow([row[0],startcount+rowcount-row[0]+1])
    else:
        with arcpy.da.UpdateCursor(out_fc,['OID@',sortfield]) as cursor:
            for row in cursor:
                cursor.updateRow([row[0],startcount+row[0]])
    return out_fc, rowcount


def SortTransectsFromSortLines(in_fc, out_fc, sort_lines=[], sortfield='sort_ID', sort_corner='LL'):
    # Alternative to SpatialSort() when sorting must be done in spatial groups
    try:
        arcpy.AddField_management(in_fc, sortfield, 'SHORT')
    except:
        pass
    if not len(sort_lines):
        base_fc, ct = SortTransectsByFeature(in_fc, 0, sort_lines, [1, sort_corner])
    else:
        sort_lines_arr = arcpy.da.FeatureClassToNumPyArray(sort_lines, ['sort', 'sort_corn'])
        base_fc, ct = SortTransectsByFeature(in_fc, 0, sort_lines, sort_lines_arr[0])
        for row in sort_lines_arr[1:]:
            next_fc, ct = SortTransectsByFeature(in_fc, ct, sort_lines, row)
            arcpy.Append_management(next_fc, base_fc)
    # arcpy.FeatureClassToFeatureClass_conversion(base_fc, arcpy.env.workspace, out_fc)
    SetStartValue(base_fc, out_fc, sortfield, start=1)
    return(out_fc)

def SortTransectsByFeature(in_fc, new_ct, sort_lines=[], sortrow=[0, 'LL']):
    out_fc = 'trans_sort{}_temp'.format(new_ct)
    if len(sort_lines):
        arcpy.SelectLayerByAttribute_management(sort_lines, "NEW_SELECTION", "sort = {}".format(sortrow[0]))
        arcpy.SelectLayerByLocation_management(in_fc, overlap_type='INTERSECT', select_features=sort_lines)
    arcpy.Sort_management(in_fc, out_fc, [['Shape', 'ASCENDING']], sortrow[1]) # Sort from lower left - this
    ct = 0
    with arcpy.da.UpdateCursor(out_fc, ['OID@', sortfield]) as cursor:
        for row in cursor:
            ct+=1
            cursor.updateRow([row[0], row[0]+new_ct])
    return(out_fc, ct)

def SetStartValue(trans_sort_1, extendedTrans, tID_fld, start=1):
    # Make sure tID_fld counts from 1
    # Work with duplicate of original transects to preserve them
    arcpy.Sort_management(trans_sort_1, extendedTrans, tID_fld)
    # If tID_fld does not count from 1, adjust the values
    with arcpy.da.SearchCursor(extendedTrans, tID_fld) as cursor:
        row = next(cursor)
    if row[0] > start:
        offset = row[0]-start
        with arcpy.da.UpdateCursor(extendedTrans, tID_fld) as cursor:
            for row in cursor:
                row[0] = row[0]-offset
                cursor.updateRow(row)
    else:
        print("First value was already {}.".format(start))
    return

def PreprocessTransects(site,old_transects=False,sort_corner='LL',sortfield='sort_ID',distance=3000):
    # In copy of transects feature class, create and populate sort field (sort_ID), and extend transects
    if not old_transects:
        old_transects = '{}_LTtransects'.format(site)
    new_transects = '{}_LTtrans_sort'.format(site)
    extTransects = '{}_extTrans'.format(site)
    # Create field trans_order and sort by that
    SpatialSort(old_transects,new_transects,sort_corner,sortfield=sortfield)
    # extend lines
    ExtendLine(new_transects,extTransects,distance)
    return extTransects


def CreateShoreBetweenInlets(shore_delineator,inletLines,out_line,shoreline_pts, proj_code=26918):
    # Ready layers for processing
    DeleteExtraFields(inletLines)
    DeleteExtraFields(shore_delineator)
    #if not arcpy.Describe(shore_delineator).spatialReference.factoryCode == proj_code:
    shore_delineator = ReProject(shore_delineator,shore_delineator+'_utm',proj_code) # Problems projecting
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
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", shoreline_pts,'1 METERS')
    # count intersecting inlet lines
    arcpy.SpatialJoin_analysis('split_temp',inletLines,"join_temp","JOIN_ONE_TO_ONE")
    #arcpy.SelectLayerByAttribute_management("join_temp", "REMOVE_FROM_SELECTION", '"FID_{}" > -1'.format(inletLines)) # invalid SQL expression
    print('CHECK THIS PROCESS. Added Dissolve operation to CreateShore... and so far it has not been tested.')
    arcpy.Dissolve_management("join_temp", out_line, [["FID_{}".format(shore_delineator)]], [['Join_Count','SUM']])
    #ReplaceFields(shoreline_pts,{'ORIG_FID':'OID@'},'SHORT')
    #ReplaceFields(out_line,{'ORIG_FID':'OID@'},'SHORT')
    return out_line

def RasterToLandPerimeter(in_raster, out_polygon, threshold, agg_dist='30 METERS', min_area='300 SquareMeters', min_hole_sz='300 SquareMeters', manualadditions=None):
    """ Raster to Polygon: DEM => Reclass => MHW line """
    home = arcpy.env.workspace
    r2p = os.path.join(home, out_polygon+'_r2p_temp')
    r2p_union = os.path.join(home, out_polygon+'_r2p_union_temp')

    # Reclassify the DEM: 1 = land above threshold; the rest is nodata
    rastertemp = arcpy.sa.Con(arcpy.sa.Raster(in_raster)>threshold, 1, None)  # temporary layer classified from threshold
    # Convert the reclass raster to a polygon
    arcpy.RasterToPolygon_conversion(rastertemp, r2p)  # polygon outlining the area above MHW
    if manualadditions: # Manually digitized any large areas missed by the lidar
        arcpy.Union_analysis([manualadditions,r2p], r2p_union, gaps='NO_GAPS')
        arcpy.AggregatePolygons_cartography(r2p_union, out_polygon, agg_dist, min_area, min_hole_sz)
    else:
        arcpy.AggregatePolygons_cartography(r2p, out_polygon, agg_dist, min_area, min_hole_sz)
    return out_polygon

def CombineShorelinePolygons(bndMTL, bndMHW, inletLines, ShorelinePts, bndpoly):
    # Use MTL and MHW contour polygons to create full barrier island shoreline polygon; Shoreline at MHW on oceanside and MTL on bayside
    # Inlet lines must intersect the MHW polygon
    union = 'union_temp'
    split_temp = 'split_temp'
    union_2 = 'union_2_temp'

    arcpy.Union_analysis([bndMTL, bndMHW], union)

    # Create layer (split_temp) of land between MTL and MHW, split at inlets
    query = 'FID_{}>0 AND FID_{}<0'.format(bndMTL, bndMHW)
    arcpy.SelectLayerByAttribute_management(union, 'NEW_SELECTION', query) # Select only MTL features
    arcpy.FeatureToPolygon_management([union, inletLines], split_temp) # Split MTL features at inlets
    arcpy.SelectLayerByAttribute_management(union, 'CLEAR_SELECTION') # Clear the selection

    arcpy.SelectLayerByLocation_management(split_temp, "INTERSECT", ShorelinePts, '#', "NEW_SELECTION") # Select MHW-MLW area on oceanside, based on intersection with shoreline points
    #Why Erase instead of union between bndMHW and split_temp? or Erase from bndMTL?
    # Union didn't work when I tried it manually. Append worked, after copying bndMHW to bndpoly
    arcpy.Erase_analysis(union, split_temp, union_2) # Erase from union layer the selected shoreline area in split
    arcpy.Dissolve_management(union_2, bndpoly, multi_part='SINGLE_PART') # Dissolve all features in union_2 to single part polygons
    print 'Select extra features for deletion\nRecommended technique: select the polygon/s to keep and then Switch Selection\n'
    return bndpoly

def DEMtoFullShorelinePoly(elevGrid, prefix, MTL, MHW, inletLines, ShorelinePts):
    bndMTL = '{}_bndpoly_mtl'.format(prefix)
    bndMHW = '{}_bndpoly_mhw'.format(prefix)
    bndpoly = '{}_bndpoly'.format(prefix)

    RasterToLandPerimeter(elevGrid, bndMTL, MTL)  # Polygon of MTL contour
    RasterToLandPerimeter(elevGrid, bndMHW, MHW)  # Polygon of MHW contour
    CombineShorelinePolygons(bndMTL, bndMHW, inletLines, ShorelinePts, bndpoly)

    #DeleteTempFiles()
    return bndpoly

def NewBNDpoly(old_boundary, modifying_feature, new_bndpoly='boundary_poly', vertexdist='25 METERS', snapdist='25 METERS'):
    # boundary = input line or polygon of boundary to be modified by newline
    typeFC = arcpy.Describe(old_boundary).shapeType
    if typeFC == "Line" or typeFC =='Polyline':
        arcpy.FeatureToPolygon_management(old_boundary,new_bndpoly,'1 METER')
    else:
        arcpy.FeatureClassToFeatureClass_conversion(old_boundary,arcpy.env.workspace,new_bndpoly)
    typeFC = arcpy.Describe(modifying_feature).shapeType
    if typeFC == "Line" or typeFC == "Polyline":
        arcpy.Densify_edit(modifying_feature, 'DISTANCE', vertexdist)
    # elif typeFC == "Point" or typeFC == "Multipoint":
    #     arcpy.PointsToLine_management(modifying_feature, modifying_feature+'_line')
    #     modifying_feature = modifying_feature+'_line'
    #     arcpy.Densify_edit(modifying_feature, 'DISTANCE', vertexdist)
    arcpy.Densify_edit(new_bndpoly,'DISTANCE',vertexdist)
    #arcpy.Densify_edit(modifying_feature,'DISTANCE',vertexdist)
    arcpy.Snap_edit(new_bndpoly,[[modifying_feature,'VERTEX',snapdist]]) # Takes a while
    return new_bndpoly # string name of new polygon

def JoinFields(targetfc, sourcefile, dest2src_fields, joinfields=['sort_ID']):
    # Add fields from sourcefile to targetfc; alter
    # If dest2src_fields is a list/tuple instead of dictionary, convert.
    if type(dest2src_fields) is list or type(dest2src_fields) is tuple:
        joinlist = dest2src_fields
        dest2src_fields = {}
        for new in joinlist:
            dest2src_fields[new] = new
    # Prepare target and source FCs: remove new field if it exists and find name of src field
    print('Deleting any fields in {} with the name of fields to be joined ({}).'.format(targetfc, dest2src_fields.keys()))
    for (dest, src) in dest2src_fields.items():
        # Remove dest field from FC if it already exists
        try: #if fieldExists(targetfc, dest):
            arcpy.DeleteField_management(targetfc, dest)
        except:
            pass
        # Search for fieldname matching 'src' field
        found = fieldExists(sourcefile, src) # if src field exists, found is True
        if not found:
            # identify most similarly named field and replace in dest2src_fields
            fieldlist = arcpy.ListFields(sourcefile, src+'*')
            if len(fieldlist) < 2:
                dest2src_fields[dest] = fieldlist[0].name
                found=True
            else:
                for f in fieldlist:
                    if f.name.endswith('_sm'):
                        dest2src_fields[dest] = f.name
                        found = True
        if not found:
            raise AttributeError("Field similar to {} was not found in {}.".format(src, sourcefile))
    # Add [src] fields from sourcefile to targetFC
    src_fnames = dest2src_fields.values()
    print('Joining fields from {} to {}: {}'.format(sourcefile, targetfc, src_fnames))
    if len(joinfields)==1:
        try:
            arcpy.JoinField_management(targetfc, joinfields, sourcefile, joinfields, src_fnames)
        except RuntimeError as e:
            print("JoinField_management produced RuntimeError: {} \nHere were the inputs:".format(e))
            print("dest2src_fields.values (src_fnames): {}".format(src_fnames))
            print("joinfields: {}".format(joinfields))
    elif len(joinfields)==2:
        arcpy.JoinField_management(targetfc, joinfields[0], sourcefile, joinfields[1], src_fnames)
    else:
        print 'joinfield accepts either one or two values only.'
    # Rename new fields from src fields
    print('Renaming the joined fields to their new names...')
    for (dest, src) in dest2src_fields.items():
        if not dest == src:
            try:
                arcpy.AlterField_management(targetfc, src, dest, dest)
            except:
                pass
    #arcpy.Delete_management(os.path.join(arcpy.env.workspace,sourcefile))
    return targetfc

def find_similar_fields(prefix, oldPts, fields=[]):
    fmapdict = {'lon': {'dest': prefix+'_Lon'},
                'lat': {'dest': prefix+'_Lat'},
                'east': {'dest': prefix+'_x'},
                'north': {'dest': prefix+'_y'},
                '_z': {'dest': prefix+'_z'},
                'slope': {'dest': 'slope'}}
    if len(fields):
        fdict = {}
        for f in fields:
            fdict[f] = fmapdict[f]
    else:
        fdict = fmapdict
    for key in fdict: # Yes, this loops through keys
        src = key
        if not fieldExists(oldPts, src):
            print('Looking for field {}'.format(src))
            # identify most similarly named field and replace in dest2src_fields
            fieldlist = arcpy.ListFields(oldPts, src+'*')
            if len(fieldlist) == 1: # if there is only one field that matches src
                src = fieldlist[0].name
            elif len(fieldlist) > 1:
                for f in fieldlist:
                    if f.name.endswith('_sm'):
                        src = f.name
            else:
                fieldlist = arcpy.ListFields(oldPts, '*'+src+'*')
                if len(fieldlist) == 1: # if there is only one field that matches src
                    src = fieldlist[0].name
                elif len(fieldlist) > 1:
                    for f in fieldlist:
                        if f.name.endswith('_sm'):
                            src = f.name
                else:
                    raise AttributeError("Field similar to {} was not found in {}.".format(src, oldPts))
                    pass
        fdict[key]['src'] = src
    return(fdict)

def geom_shore2trans(transect, tID, shoreline, in_pts, slp_fld, proximity=25):
    # for input transect geometry, get slope at nearest shoreline point and XY at intersect
    # 1 second per transect for ~2000 input points
    slp = np.nan
    slxpt = arcpy.Point(np.nan, np.nan)
    for srow in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
        sline = srow[0] # polyline geometry
        # Set SL_x and SL_y to point where transect intersects shoreline
        if not transect.disjoint(sline):
            slxpt = transect.intersect(sline, 1)[0]
    # Get the closest shoreline point for the slope value
    shortest_dist = float(proximity)
    # found = False
    for prow in arcpy.da.SearchCursor(in_pts, [slp_fld, "SHAPE@"]):
        pt_distance = transect.distanceTo(prow[1])
        if pt_distance < shortest_dist:
            shortest_dist = pt_distance
            # found=True
            # print('slope: {}'.format(prow[0]))
            slp = prow[0]
    return(tID, [slxpt.X, slxpt.Y, slp])

def add_shorelinePts2Trans(in_trans, in_pts, shoreline, tID_fld='sort_ID', proximity=25, verbose=True):
    start = time.clock()
    fmapdict = find_similar_fields(prefix, in_pts, ['slope'])
    slp_fld = fmapdict['slope']['src']
    df = pd.DataFrame(columns=['SL_x', 'SL_y', 'Bslope'], dtype='float64')
    df.index.name = tID_fld
    for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = trow[0]
        tID = trow[1]
        newrow = geom_shore2trans(transect, tID, shoreline, in_pts, slp_fld, proximity)
        df.loc[newrow[0], ['SL_x', 'SL_y', 'Bslope']] = newrow[1]
        if verbose:
            if tID % 100 < 1:
                print('Duration at transect {}: {}'.format(tID, print_duration(start, True)))
    print_duration(start)
    return(df)

def geom_dune2trans(transect, tID, in_pts, z_fld, proximity=25):
    z = x = y = np.nan
    shortest_dist = float(proximity)
    for prow in arcpy.da.SearchCursor(in_pts, [z_fld, "SHAPE@X", "SHAPE@Y"]):
        pt_distance = transect.distanceTo(arcpy.Point(prow[1], prow[2]))
        if pt_distance < shortest_dist:
            shortest_dist = pt_distance
            x = prow[1]
            y = prow[2]
            z = prow[0]
    return(tID, [x, y, z])

def add_dunePts2Trans(in_trans, in_pts, shoreline, tID_fld='sort_ID', proximity=25, verbose=True):
    start = time.clock()
    fmapdict = find_similar_fields(prefix, in_pts, ['_z'])
    z_fld = fmapdict['_z']['src']
    df = pd.DataFrame(columns=[prefix+'_x', prefix+'_y', prefix+'_z'], dtype='float64')
    df.index.name = tID_fld
    for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = trow[0]
        tID = trow[1]
        newrow = geom_dune2trans(transect, tID, in_pts, z_fld, proximity)
        df.loc[newrow[0], [prefix+'_x', prefix+'_y', prefix+'_z']] = newrow[1]
        if verbose:
            if tID % 100 < 1:
                print('Duration at transect {}: {}'.format(tID, print_duration(start, True)))
    print_duration(start)
    return(df)

def add_Pts2Trans(in_trans, dl_pts, dh_pts, sl_pts, shoreline, tID_fld='sort_ID', proximity=25, verbose=True):
    # For each transect, get the XY and Z/slope of DL, DH, and SL points
    # Duration for ParkerRiver: 55 minutes
    start = time.clock()
    fmapdict = find_similar_fields('DL', dl_pts, ['_z'])
    dlZ_fld = fmapdict['_z']['src']
    fmapdict = find_similar_fields('DH', dh_pts, ['_z'])
    dhZ_fld = fmapdict['_z']['src']
    fmapdict = find_similar_fields('SL', sl_pts, ['slope'])
    slp_fld = fmapdict['slope']['src']
    df = pd.DataFrame(columns=['DL_x', 'DL_y', 'DL_z', 'DH_x', 'DH_y', 'DH_z', 'SL_x', 'SL_y', 'Bslope'], dtype='float64')
    df.index.name = tID_fld
    for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = trow[0]
        tID = trow[1]
        newrow = geom_dune2trans(transect, tID, dl_pts, dlZ_fld, proximity)
        df.loc[newrow[0], ['DL_x', 'DL_y', 'DL_z']] = newrow[1]
        newrow = geom_dune2trans(transect, tID, dh_pts, dhZ_fld, proximity)
        df.loc[newrow[0], ['DH_x', 'DH_y', 'DH_z']] = newrow[1]
        newrow = geom_shore2trans(transect, tID, shoreline, sl_pts, slp_fld, proximity)
        df.loc[newrow[0], ['SL_x', 'SL_y', 'Bslope']] = newrow[1]
        if verbose:
            if tID % 100 < 1:
                print('Duration at transect {}: {}'.format(tID, print_duration(start, True)))
    print_duration(start)
    return(df)

def add_shorelinePts2Trans_v1(in_trans, in_pts, shoreline, prefix='SL', tID_fld='sort_ID', snaptoline_on=False, proximity=25, verbose=True):
    # 8 minutes
    start = time.clock()
    fmapdict = find_similar_fields(prefix, in_pts, ['slope'])
    slp_fld = fmapdict['slope']['src']
    df = pd.DataFrame(columns=[prefix+'_x', prefix+'_y', 'Bslope'], dtype='float64')
    df.index.name = tID_fld
    # ~ 50 transects per minute
    if verbose:
        print('Looping through transects to find nearest point within {} meters...'.format(proximity))
    for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = trow[0]
        tID = trow[1]
        for srow in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
            sline = srow[0] # polyline geometry
            # Set SL_x and SL_y to point where transect intersects shoreline
            if not transect.disjoint(sline):
                slxpt = transect.intersect(sline, 1)[0]
                df.loc[tID, [prefix+'_x', prefix+'_y', 'Bslope']] = [slxpt.X, slxpt.Y, np.nan]
        # Get the closest shoreline point for the slope value
        shortest_dist = float(proximity)
        # found = False
        for prow in arcpy.da.SearchCursor(in_pts, [slp_fld, "SHAPE@"]):
            pt_distance = transect.distanceTo(prow[1])
            if pt_distance < shortest_dist:
                shortest_dist = pt_distance
                # found=True
                # print('slope: {}'.format(prow[0]))
                df.loc[tID, ['Bslope']] = [prow[0]] # overwrite Bslope if pt is closer
        if verbose:
            if tID % 100 < 1:
                print('Duration at transect {}: {}'.format(tID, print_duration(start, True)))
    print_duration(start)
    return(df)

def find_ClosestPt2Trans(in_trans, in_pts, prefix, tID_fld='sort_ID', snaptoline_on=False, proximity=25, verbose=True):
    # About 1 minutes per transect
    start = time.clock()
    if verbose:
        print('Getting name of Z field...')
    fmapdict = find_similar_fields(prefix, in_pts)
    z_fld = fmapdict['_z']['src']
    df = pd.DataFrame(columns=[tID_fld, prefix+'_x', prefix+'_y', prefix+'_z', prefix+'_dist2tran'], dtype='float64')
    df.index.name = tID_fld
    if verbose:
        print('Looping through transects to find nearest point within {} meters...'.format(proximity))
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@", tID_fld)):
        transect = row[0]
        tID = row[1]
        # buff = transect.buffer(proximity)
        shortest_dist = float(proximity)
        found = False
        for prow in arcpy.da.SearchCursor(in_pts, ["SHAPE@X", "SHAPE@Y", z_fld, "OID@"]):
            in_pt = arcpy.Point(X=prow[0], Y=prow[1], Z=prow[2], ID=prow[3])
            # if not buff.disjoint(in_pt):
            if transect.distanceTo(in_pt) < shortest_dist:
                shortest_dist = transect.distanceTo(in_pt)
                pt = in_pt
                found = True
        if found:
            newrow = {tID_fld:tID, prefix+'_x':pt.X, prefix+'_y':pt.Y, prefix+'_z':pt.Z, prefix+'_dist2tran':shortest_dist}
            df = df.append(newrow, ignore_index=True)
        if verbose:
            if tID % 20 < 1:
                print('Progress check at {}...'.format(tID))
                duration = print_duration(start)
    df.index = df[tID_fld]
    df.drop(tID_fld, axis=1, inplace=True)
    duration = print_duration(start)
    return(df)

def measure_Dist2Inlet(shoreline, in_trans, tID_fld='sort_ID'):
    df = pd.DataFrame(columns=[tID_fld, 'Dist2Inlet'])
    for row in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
        line = row[0]
        for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
            transect = trow[0]
            tID = trow[1]
            if not line.disjoint(transect): #line and transect overlap
                shoreseg = line.cut(transect)
                mindist = min(shoreseg[0].length, shoreseg[1].length)
                df = df.append({tID_fld:tID, 'Dist2Inlet':mindist}, ignore_index=True)
    df.index = df[tID_fld]
    df.drop(tID_fld, axis=1, inplace=True)
    return(df)

def TransectsToContinuousRaster(in_trans, out_rst, cell_size, IDfield='sort_ID'):
    # Create raster of sort_ID - each cell value indicates its nearest transect
    # in_trans = extTrans_tidy (only sort_ID field is necessary)
    # out_rst = {}{}_rstTransID
    #trans_rst = 'rst_transID_temp'
    #arcpy.PolylineToRaster_conversion(in_trans, IDfield, trans_rst, cellsize=5)
    outEucAll = arcpy.sa.EucAllocation(in_trans, maximum_distance=50, cell_size=cell_size, source_field=IDfield)
    outEucAll.save(out_rst)
    return out_rst

def JoinFCtoRaster(in_tbl, rst_ID, out_rst, IDfield='sort_ID'):
    # Join fields from in_tbl to rst_ID to create new out_rst
    RemoveLayerFromMXD('rst_lyr') # in case of reprocessing
    arcpy.MakeTableView_management(in_tbl, 'tableview')
    arcpy.MakeRasterLayer_management(rst_ID, 'rst_lyr')
    arcpy.AddJoin_management('rst_lyr', 'Value', 'tableview', IDfield)
    arcpy.CopyRaster_management('rst_lyr', out_rst)
    return out_rst

def FCtoRaster(in_fc, in_ID, out_rst, IDfield, home, fill=False, cell_size=5):
    # Convert feature class to continuous raster in which output raster takes the values from the nearest feature (Euclidean distance).
    # in_ID could = original tidyTrans, existing ID raster, or ID raster to be created
    # If an ID raster does not exist, it will be created from the specified ID field of the feature class.
    # Optionally replace Null values with fill.
    if fill:
        fill_fc = in_fc+'_fill'
        arcpy.FeatureClassToFeatureClass_conversion(in_fc, home, fill_fc)
        fields=[]
        for f in arcpy.ListFields(fill_fc):
            if f.type!='String':  # list all fields that are NOT string type
                fields.append(f.name)
        ReplaceValueInFC(fill_fc, None, fill, fields)
    else:
        fill_fc = in_fc
    # Create/get ID raster (rst_ID)
    if not arcpy.Exists(in_ID):
        print('{} (in_ID) does not exist. Creating raster from {}.'.format(in_ID, in_fc))
        # If in_ID does not exist, it will be created as a raster from in_fc
        #rst_ID = TransectsToContinuousRaster(in_trans=in_fc, out_rst=in_ID, cell_size=cell_size, IDfield=IDfield)
        outEucAll = arcpy.sa.EucAllocation(in_fc, maximum_distance=50, cell_size=cell_size, source_field=IDfield)
        outEucAll.save(in_ID)
        rst_ID = in_ID
    elif 'Feature' in arcpy.Describe(in_ID).dataType:
        print('{} (in_ID) is vector. Creating raster.'.format(in_ID))
        # if in_ID does exist and is vector
        rst_ID = os.path.basename(in_ID)+'_IDrst'
        #rst_ID = TransectsToContinuousRaster(in_trans=in_ID, out_rst=rst_ID, cell_size=cell_size, IDfield=IDfield)
        outEucAll = arcpy.sa.EucAllocation(in_ID, maximum_distance=50, cell_size=cell_size, source_field=IDfield)
        outEucAll.save(rst_ID)
    else:  # if in_ID exists and is not vector, assume it is the ID raster
        print('Using {} (in_ID) as ID raster.'.format(in_ID))
        rst_ID = in_ID

    # Join all fields to raster
    JoinFCtoRaster(fill_fc, rst_ID, out_rst, IDfield)
    print('Raster {} created from {}.'.format(out_rst, in_fc))
    return fill_fc, out_rst

def TransectsToPointsDF(in_trans, barrierBoundary, out_tidyclipped='tidytrans_clipped', fc_out=False, tID_fld='sort_ID', step=5):
    start = time.clock()
    out_tidyclipped='tidytrans_clipped2island'
    if not arcpy.Exists(out_tidyclipped):
        arcpy.Clip_analysis(in_trans, barrierBoundary, out_tidyclipped)
    print('Getting points every 5m along each transect and saving in dataframe...')
    # Initialize empty dataframe
    df = pd.DataFrame(columns=[tID_fld, 'seg_x', 'seg_y'])
    # Get shape object and sort_ID value for each transects
    with arcpy.da.SearchCursor(out_tidyclipped, ("SHAPE@", tID_fld)) as cursor:
        for row in cursor:
            ID = row[1]
            line = row[0]
            for i in range(0, int(line.length), step):
                pt = line.positionAlongLine(i)[0]
                newrow = {tID_fld:ID, 'seg_x':pt.X, 'seg_y':pt.Y}
                # add to DF
                df = df.append(newrow, ignore_index=True)
    if fc_out:
        print('Converting new dataframe to feature class...')
        fc = '{}_{}mPts_unsorted'.format(in_trans, step)
        DFtoFC(df, fc, id_fld=tID_fld, spatial_ref = arcpy.Describe(in_trans).spatialReference)
        duration = print_duration(start)
        return(df, fc)
    duration = print_duration(start)
    return(df)

def ShorelineToTrans_PD(extendedTransects, trans_df, inPtsDict, IDfield, proj_code, disttolerance=25, fill=-99999):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']
    shoreline = inPtsDict['shoreline']
    ShorelinePts = inPtsDict['ShorelinePts']
    shl2trans = 'SHL2trans_temp'
    shljoin = 'shljoin_temp'
    home = arcpy.env.workspace
    arcpy.Intersect_analysis((shoreline, extendedTransects), shl2trans, output_type='POINT')
    #FIXME: shljoin = JOIN closest feature in ShorelinePts to shl2trans
    #fmap = 'sort_ID "sort_ID" true true false 2 Short 0 0 ,First,#,SHL2trans_temp,sort_ID,-1,-1; ID "ID" true true false 4 Float 0 0 ,First,#,\\IGSAGIEGGS-CSGG\Thieler_Group\Commons_DeepDive\DeepDive\Delmarva\Assateague\2014\Assateague2014.gdb\Assateague2014_SLpts,ID,-1,-1'
    # arcpy.SpatialJoin_analysis(shl2trans, os.path.join(home, ShorelinePts), 'join_temp','#','#', fmap, "CLOSEST", pt2trans_disttolerance) # create join_temp

def ShoreIntersectToTrans_PD(trans_df, shljoin, IDfield, disttolerance=25, fill=-99999):
    shljoin_df = FCtoDF(shljoin, xy=True, dffields=[IDfield, 'slope', 'Distance'], fid=True)
    shljoin_df.rename(index=str, columns={'slope':'Bslope', 'SHAPE@X':'SL_x','SHAPE@Y':'SL_y', 'OID@':'slpts_id'}, inplace=True)
    for i, row in shljoin_df.iterrows():
        if row['Distance'] > disttolerance:
            shljoin_df.ix[i, 'Bslope'] = fill
    shljoin_df = shljoin_df.drop('Distance', axis=1)
    shljoin_df.index.name = IDfield
    trans_df = join_columns(trans_df, shljoin_df, id_fld=IDfield)
    # JoinDFtoFC(shljoin_df, extendedTransects, IDfield)
    # return extendedTransects
    return(trans_df, shljoin_df)

def ArmorLineToTrans_PD(in_trans, trans_df, armorLines, IDfield, proj_code, elevGrid_5m):
    #FIXME: How do I know which point will be encountered first? - don't want those in back to take the place of
    arm2trans="arm2trans"
    armorfields = ['Arm_x','Arm_y','Arm_z']
    if not arcpy.Exists(armorLines) or not int(arcpy.GetCount_management(armorLines).getOutput(0)):
        print('Armoring file either missing or empty so we will proceed without armoring data. If shorefront tampering is present at this site, cancel the operations to digitize.')
        arm2trans_df = pd.DataFrame(columns=armorfields, data=np.nan, index=trans_df.index)
    else:
        # arcpy.GetCount_management(armorLines).getOutput(0)
        # Create armor points with XY fields
        arcpy.Intersect_analysis((armorLines, in_trans), arm2trans, output_type='POINT')
        print('Getting elevation of beach armoring by extracting elevation values to arm2trans points.')
        #FIXME: might need to convert multipart to singlepart before running Extract
        arcpy.sa.ExtractMultiValuesToPoints(arm2trans, [[elevGrid_5m, 'z_tmp']]) # this produced a Background Processing error: temporary solution is to disable background processing in the Geoprocessing Options
        arm2trans_df = FCtoDF(arm2trans, xy=True, dffields=[IDfield, 'z_tmp'])
        arm2trans_df.rename(index=str, columns={'z_tmp':'Arm_z', 'SHAPE@X':'Arm_x','SHAPE@Y':'Arm_y'}, inplace=True)
        arm2trans_df.index.name = IDfield
    # Join
    trans_df = join_columns(trans_df, arm2trans_df)
    # JoinDFtoFC(arm2trans_df, in_trans, IDfield)
    # return(in_trans)
    return(trans_df)

def calc_BeachWidth(in_trans, trans_df, maxDH, tID_fld='sort_ID', MHW=''):
    # v3 (v1: arcpy, v2: pandas, v3: pandas with snapToLine() from arcpy)
    # To find dlow proxy, uses code written by Ben in Matlab and converted to pandas by Emily
    # Adds snapToLine() polyline geometry method from arcpy
    # add (or recalculate) elevation fields adjusted to MHW
    trans_df = adjust2mhw(trans_df, MHW)
    # initialize series
    sl2dl = pd.Series(np.nan, index=trans_df.index, name='DistDL')
    sl2dh = pd.Series(np.nan, index=trans_df.index, name='DistDH')
    sl2arm = pd.Series(np.nan, index=trans_df.index, name='DistArm') # dtype will 'object'
    uBW = pd.Series(np.nan, index=trans_df.index, name='uBW')
    uBH = pd.Series(np.nan, index=trans_df.index, name='uBH')
    feat = pd.Series(np.nan, index=trans_df.index, name='ub_feat') # dtype will 'object'
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = row[0]
        tID = row[1]
        tran = trans_df.ix[tID]
        if not np.isnan(tran.DL_x): # RuntimeError: Point: Input value is not numeric
            ptDL = transect.snapToLine(arcpy.Point(tran['DL_x'], tran['DL_y']))
            sl2dl[tID] = np.hypot(tran['SL_x']- ptDL[0].X, tran['SL_y'] - ptDL[0].Y)
        if not np.isnan(tran.DH_x):
            ptDH = transect.snapToLine(arcpy.Point(tran['DH_x'], tran['DH_y']))
            sl2dh[tID] = np.hypot(tran['SL_x'] - ptDH[0].X, tran['SL_y'] - ptDH[0].Y)
        if not np.isnan(tran.Arm_x):
            ptArm = transect.snapToLine(arcpy.Point(tran['Arm_x'], tran['Arm_y']))
            sl2arm[tID] = np.hypot(tran['SL_x'] - ptArm[0].X, tran['SL_y'] - ptArm[0].Y)
        if not np.isnan(tran.DL_x):
            uBW[tID] = sl2dl[tID]
            uBH[tID] = tran['DL_zmhw']
            feat[tID] = 'DL'
        elif tran.DH_zmhw <= maxDH:
            uBW[tID] = sl2dh[tID]
            uBH[tID] = tran['DH_zmhw']
            feat[tID] = 'DH'
        elif not np.isnan(tran.Arm_x):
            uBW[tID] = sl2arm[tID]
            uBH[tID] = tran['Arm_zmhw']
            feat[tID] = 'Arm'
        else: # If there is no DL equivalent, BW and BH = null
            # uBW[tID] = uBH[tID] = np.nan
            continue
    # Add new uBW and uBH fields to trans_df
    bw_df = pd.concat([sl2dl, sl2dh, sl2arm, uBW, uBH, feat], axis=1)
    # pts_df = (pts_df.drop(pts_df.axes[1].intersection(bw_df.axes[1]), axis=1).join(bw_df, on=tID_fld, how='outer'))
    trans_df = join_columns(trans_df, bw_df)
    return(trans_df)

def calc_BeachWidth_fill(in_trans, trans_df, maxDH, tID_fld='sort_ID', MHW='', fill=-99999):
    # v3 (v1: arcpy, v2: pandas, v3: pandas with snapToLine() from arcpy)
    # To find dlow proxy, uses code written by Ben in Matlab and converted to pandas by Emily
    # Adds snapToLine() polyline geometry method from arcpy

    # replace nan's with fill for cursor operations; may actually be necessary to work with nans... performing calculations with fill results in inaccuracies
    if trans_df.isnull().values.any():
        nan_input = True
        trans_df.fillna(fill, inplace=True)
    else:
        nan_input = False
    # add (or recalculate) elevation fields adjusted to MHW
    trans_df = adjust2mhw(trans_df, MHW, ['DH_z', 'DL_z', 'Arm_z'], fill)
    # initialize df
    bw_df = pd.DataFrame(fill, index=trans_df.index, columns= ['DistDL', 'DistDH', 'DistArm', 'uBW', 'uBH', 'ub_feat'], dtype='f8')
    # initialize series
    # feat = pd.Series(fill, index=trans_df.index, dtype='object', name='ub_feat') # dtype will 'object'
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = row[0]
        tID = row[1]
        tran = trans_df.ix[tID]
        if int(tran.DL_x) != int(fill):
            ptDL = transect.snapToLine(arcpy.Point(tran['DL_x'], tran['DL_y']))
            bw_df['DistDL'].iloc[tID] = np.hypot(tran['SL_x']- ptDL[0].X, tran['SL_y'] - ptDL[0].Y)
        if int(tran.DH_x) != int(fill):
            ptDH = transect.snapToLine(arcpy.Point(tran['DH_x'], tran['DH_y']))
            bw_df['DistDH'].iloc[tID] = np.hypot(tran['SL_x'] - ptDH[0].X, tran['SL_y'] - ptDH[0].Y)
        if int(tran.Arm_x) != int(fill):
            ptArm = transect.snapToLine(arcpy.Point(tran['Arm_x'], tran['Arm_y']))
            bw_df['DistArm'].iloc[tID] = np.hypot(tran['SL_x'] - ptArm[0].X, tran['SL_y'] - ptArm[0].Y)
        if int(tran.DL_x) != int(fill):
            bw_df['uBW'].iloc[tID] = bw_df['DistDL'].iloc[tID]
            bw_df['uBH'].iloc[tID] = tran['DL_zmhw']
            bw_df['ub_feat'].iloc[tID] = 'DL'
        elif int(tran.DH_x) != int(fill) and tran.DH_zmhw <= maxDH:
            bw_df['uBW'].iloc[tID] = bw_df['DistDH'].iloc[tID]
            bw_df['uBH'].iloc[tID] = tran['DH_zmhw']
            bw_df['ub_feat'].iloc[tID] = 'DH'
        elif int(tran.Arm_x) != int(fill):
            bw_df['uBW'].iloc[tID] = bw_df['DistArm'].iloc[tID]
            bw_df['uBH'].iloc[tID] = tran['Arm_zmhw']
            bw_df['ub_feat'].iloc[tID] = 'Arm'
        else:
            continue
    # Add new uBW and uBH fields to trans_df
    trans_df = join_columns(trans_df, bw_df)
    if nan_input: # restore nan values
        trans_df.replace(fill, np.nan, inplace=True)
    return(trans_df)

def calc_BeachWidth_fill_v1(in_trans, trans_df, maxDH, tID_fld='sort_ID', MHW='', fill=-99999):
    # v3 (v1: arcpy, v2: pandas, v3: pandas with snapToLine() from arcpy)
    # To find dlow proxy, uses code written by Ben in Matlab and converted to pandas by Emily
    # Adds snapToLine() polyline geometry method from arcpy

    # replace nan's with fill for cursor operations; may actually be necessary to work with nans... performing calculations with fill results in inaccuracies
    if trans_df.isnull().values.any():
        nan_input = True
        trans_df.fillna(fill, inplace=True)
    else:
        nan_input = False
    # add (or recalculate) elevation fields adjusted to MHW
    trans_df = adjust2mhw(trans_df, MHW, ['DH_z', 'DL_z', 'Arm_z'], fill)
    # initialize df
    bw_df = pd.DataFrame(fill, index=trans_df.index, columns= ['DistDL', 'DistDH', 'DistArm', 'uBW', 'uBH', 'ub_feat'], dtype='f8')
    # initialize series
    sl2dl = pd.Series(fill, index=trans_df.index, dtype='f8', name='DistDL')
    sl2dh = pd.Series(fill, index=trans_df.index, dtype='f8', name='DistDH')
    sl2arm = pd.Series(fill, index=trans_df.index, dtype='f8', name='DistArm') # dtype will 'object'
    uBW = pd.Series(fill, index=trans_df.index, dtype='f8', name='uBW')
    uBH = pd.Series(fill, index=trans_df.index, dtype='f8', name='uBH')
    feat = pd.Series(fill, index=trans_df.index, dtype='object', name='ub_feat') # dtype will 'object'
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = row[0]
        tID = row[1]
        tran = trans_df.ix[tID]
        # if not np.isnan(tran.DL_x): # RuntimeError: Point: Input value is not numeric
        if int(tran.DL_x) != int(fill):
            ptDL = transect.snapToLine(arcpy.Point(tran['DL_x'], tran['DL_y']))
            sl2dl[tID] = np.hypot(tran['SL_x']- ptDL[0].X, tran['SL_y'] - ptDL[0].Y)
        # if not np.isnan(tran.DH_x):
        if int(tran.DH_x) != int(fill):
            ptDH = transect.snapToLine(arcpy.Point(tran['DH_x'], tran['DH_y']))
            sl2dh[tID] = np.hypot(tran['SL_x'] - ptDH[0].X, tran['SL_y'] - ptDH[0].Y)
        # if not np.isnan(tran.Arm_x):
        if int(tran.Arm_x) != int(fill):
            ptArm = transect.snapToLine(arcpy.Point(tran['Arm_x'], tran['Arm_y']))
            sl2arm[tID] = np.hypot(tran['SL_x'] - ptArm[0].X, tran['SL_y'] - ptArm[0].Y)
        # if not np.isnan(tran.DL_x):
        if int(tran.DL_x) != int(fill):
            uBW[tID] = sl2dl[tID]
            uBH[tID] = tran['DL_zmhw']
            feat[tID] = 'DL'
        # elif tran.DH_zmhw <= maxDH:
        elif int(tran.DH_x) != int(fill) and tran.DH_zmhw <= maxDH:
            uBW[tID] = sl2dh[tID]
            uBH[tID] = tran['DH_zmhw']
            feat[tID] = 'DH'
        # elif not np.isnan(tran.Arm_x):
        elif int(tran.Arm_x) != int(fill):
            uBW[tID] = sl2arm[tID]
            uBH[tID] = tran['Arm_zmhw']
            feat[tID] = 'Arm'
        else: # If there is no DL equivalent, BW and BH = null
            # uBW[tID] = uBH[tID] = np.nan
            continue
    # Add new uBW and uBH fields to trans_df
    bw_df = pd.concat([sl2dl, sl2dh, sl2arm, uBW, uBH, feat], axis=1)
    # pts_df = (pts_df.drop(pts_df.axes[1].intersection(bw_df.axes[1]), axis=1).join(bw_df, on=tID_fld, how='outer'))
    trans_df = join_columns(trans_df, bw_df)
    if nan_input: # restore nan values
        trans_df.replace(fill, np.nan, inplace=True)
    return(trans_df)

def calc_IslandWidths(in_trans, barrierBoundary, out_clipped='clip2island', tID_fld='sort_ID'):
    home = arcpy.env.workspace
    if not arcpy.Exists(out_clipped):
        print('Clipping the transect to the barrier island boundaries...')
        arcpy.Clip_analysis(os.path.join(home, in_trans), os.path.join(home, barrierBoundary), out_clipped) # ~30 seconds
    # WidthPart - spot-checking verifies the results, but it should additionally include a check to ensure that the first transect part encountered intersects the shoreline
    print('Getting the width along each transect of the oceanside land (WidthPart)...')
    # could eliminate Multi to Single using
    out_clipsingle = out_clipped + 'Single_temp'
    if not arcpy.Exists(out_clipsingle):
        arcpy.MultipartToSinglepart_management(out_clipped, out_clipsingle)
    clipsingles = FCtoDF(out_clipsingle, dffields = ['SHAPE@LENGTH', tID_fld], length=True)
    widthpart = clipsingles.groupby(tID_fld)['SHAPE@LENGTH'].first()
    widthpart.name = 'WidthPart'
    # WidthFull
    print('Getting the width along each transect of the entire barrier (WidthFull)...')
    verts = FCtoDF(out_clipped, id_fld=tID_fld, explode_to_points=True) #FIXME: throws RuntimeError at line 17 arr = arcpy.da.FeatureClassToNumPyArray(os.path.join(arcpy.env.workspace, fc), fcfields, null_value=fill, explode_to_points=explode_to_points) #FIXME: throws error
    d = verts.groupby(tID_fld)['SHAPE@X', 'SHAPE@Y'].agg(lambda x: x.max() - x.min())
    widthfull = np.hypot(d['SHAPE@X'], d['SHAPE@Y'])
    widthfull.name = 'WidthFull'
    # WidthLand
    print('Getting the width along each transect of above water portion of the barrier (WidthLand)...')
    clipped = FCtoDF(out_clipped, dffields = ['SHAPE@LENGTH', tID_fld], length=True, verbose=False)
    widthland = clipped.groupby(tID_fld)['SHAPE@LENGTH'].first()
    widthland.name = 'WidthLand'
    # Combine into DF
    widths_df = pd.DataFrame({'WidthFull':widthfull, 'WidthLand':widthland, 'WidthPart':widthpart}, index=widthfull.index)
    return(widths_df)

def FCtoDF(fc, xy=False, dffields=[], fill=-99999, id_fld=False, extra_fields=[], verbose=True, fid=False, explode_to_points=False, length=False):
    # Convert FeatureClass to pandas.DataFrame with np.nan values
    # 1. Convert FC to Numpy array
    if explode_to_points:
        message = 'Converting feature class vertices to array with X and Y...'
        fcfields = [id_fld, 'SHAPE@X', 'SHAPE@Y', 'OID@']
    else:
        fcfields = [f.name for f in arcpy.ListFields(fc)]
        if xy:
            message = 'Converting feature class to array with X and Y...'
            fcfields += ['SHAPE@X','SHAPE@Y']
        else:
            message = 'Converting feature class to array...'
        if fid:
            fcfields += ['OID@']
        if length:
            fcfields += ['SHAPE@LENGTH']
    if verbose:
        print(message)
    arr = arcpy.da.FeatureClassToNumPyArray(os.path.join(arcpy.env.workspace, fc), fcfields, null_value=fill, explode_to_points=explode_to_points)
    # 2. Convert array to dict
    if verbose:
        print('Converting array to dataframe...')
    if not len(dffields):
        dffields = list(arr.dtype.names)
    else:
        if xy:
            dffields += ['SHAPE@X','SHAPE@Y']
        if fid:
            dffields += ['OID@']
        if length:
            dffields += ['SHAPE@LENGTH']
    dict1 = {}
    for f in dffields:
        if np.ndim(arr[f]) < 2:
            dict1[f] = arr[f]
    # 3. Convert dict to DF
    if not id_fld:
        df = pd.DataFrame(dict1)
    else:
        df = pd.DataFrame(dict1, index=arr[id_fld])
        df.index.name = id_fld
        # df.drop(id_fld, axis=1, inplace=True)
    # replace fill values with NaN values
    df.replace(fill, np.nan, inplace=True) # opposite: df.fillna(fill, inplace=True)
    if len(extra_fields) > 0:
        df.drop(extra_fields, axis=1, inplace=True, errors='ignore')
    return(df)

def JoinDFtoFC(df, in_fc, join_id, target_id=False, out_fc='', overwrite=True, fill=-99999, verbose=True):
    if not target_id:
        target_id=join_id
    # If out_fc specified, initialize output FC with a copy of input
    if not len(out_fc):
        out_fc = in_fc
    else:
        arcpy.FeatureClassToFeatureClass_conversion(in_fc, arcpy.env.workspace, out_fc)
    # Use arcpy.da.ExtendTable() to join DF
    if df.index.name in df.columns:
        df.drop(df.index.name, axis=1, inplace=True)
    arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
    if overwrite:
        arcpy.da.ExtendTable(out_fc, target_id, arr, join_id, append_only=False)
    else:
        arcpy.da.ExtendTable(out_fc, target_id, arr, join_id, append_only=True)
    return(out_fc)

def JoinDFtoFC_v1(df, in_fc, join_id, target_id=False, out_fc='', join_fields=[], target_fields=[], fill=-99999, verbose=True):
    # Convert DF to table and join to FC; overwrite fields in target with joined fields
    # Default overwrites target fields with join_fields
    if not target_id:
        target_id=join_id
    # Convert DF to Table
    if verbose:
        print('Converting the dataframe to a geodatabase table...')
    tbl = os.path.join(arcpy.env.workspace, os.path.basename(in_fc) + 'join_temp')
    DFtoTable(df, tbl, fill)
    # Copy the input FC to initialize the FC to be joined
    if not len(out_fc): # if out_fc is blank,
        out_fc = in_fc
    else:
        print('Initializing the output FC with a copy of the input...')
        arcpy.FeatureClassToFeatureClass_conversion(in_fc, arcpy.env.workspace, out_fc)
    # Delete fields from target FC
    if verbose:
        print('Deleting any overlapping fields from the target features...')
    if not len(join_fields):
        # fields to delete from target
        join_fields = df.columns.drop([target_id]+target_fields, errors='ignore') #arr.dtype.names
        # keep_flds = target_id + target_fields
    else:
        try:
            join_fields.remove(target_id)
        except ValueError:
            pass
    keep_flds = [x.name for x in arcpy.ListFields(out_fc) if not x.name in join_fields] # fields that should not be deleted
    DeleteExtraFields(out_fc, keep_flds)
    # arcpy.DeleteField_management(out_fc, join_fields)
    # for fld in join_fields:
    #     if not fld in target_fields and not fld == target_id:
    #         try: #if fieldExists(targetfc, dest):
    #             arcpy.DeleteField_management(out_fc, fld)
    #         except:
    #             pass
    # Perform join
    if verbose:
        print('Performing join...')
    arcpy.JoinField_management(out_fc, target_id, tbl, join_id, join_fields) # Failing
    return(out_fc)

def DFtoFC(df, fc, spatial_ref, id_fld='', xy=["seg_x", "seg_y"], keep_fields=[], fill=-99999):
    # Create FC from DF; default will only copy XY and ID fields
    # using too many fields with a large dataset will fail
    # Convert DF to array
    if keep_fields == 'all':
        keep_fields = df.columns
    else:
        keep_fields += xy + [id_fld]
    arr = (df.select_dtypes(exclude=['object'])
             .drop(df.columns.drop(keep_fields, errors='ignore'), errors='ignore', axis=1)
             .astype('f8')
             .fillna(fill)
             .to_records())
    # Convert array to FC
    fc = os.path.join(arcpy.env.workspace, os.path.basename(fc)) # set fc path
    arcpy.Delete_management(fc) # delete if already exists
    arcpy.da.NumPyArrayToFeatureClass(arr, fc, xy, spatial_ref)
    return(fc)

def DFtoFC_large(pts_df, outFC_pts, spatial_ref, df_id='SplitSort', xy=["seg_x", "seg_y"], fill=-99999, verbose=True):
    # Create FC from DF using only XY and ID; then join the DF to the new FC
    # 1. Create pts FC
    if verbose:
        print('Converting points DF to FC...')
    outFC_pts = DFtoFC(df=pts_df, fc=outFC_pts, spatial_ref=spatial_ref, id_fld=df_id, xy=xy, keep_fields=[], fill=fill)
    arr = pts_df.select_dtypes(exclude=['object']).fillna(fill).to_records()
    arcpy.da.ExtendTable(outFC_pts, df_id, arr, df_id, append_only=False) # Takes a long time
    return(outFC_pts)

def DFtoFC_2parts(pts_df, outFC_pts, trans_df, trans_fc, spatial_ref, df_id='SplitSort', group_id='sort_ID', xy=["seg_x", "seg_y"], pt_flds=[], group_flds=[], fill=-99999, verbose=True):
    # Create FC from DF using only XY and ID; then join the DF to the new FC
    # 1. Create FC of only pt fields
    if verbose:
        print('Converting points DF to FC...')
    outFC_pts = DFtoFC(df=pts_df, fc=outFC_pts, spatial_ref=spatial_ref, id_fld=df_id, xy=xy, keep_fields=pt_flds, fill=fill)
    # 2. Create FC of transect fields by joining back to extendedTransects
    if verbose:
        print('Converting trans DF to FC...')
    group_fc = JoinDFtoFC(trans_df, trans_fc, group_id, out_fc=trans_fc+'_fromDF', fill=fill, verbose=verbose)
    # 3. Join transect fields to points in ArcPy
    missing_fields = fieldsAbsent(outFC_pts, group_flds)
    # need to make group_fc a layer before joining?
    arcpy.JoinField_management(outFC_pts, group_id, group_fc, group_id, missing_fields)
    return(outFC_pts, group_fc)

def JoinDFtoRaster(df, rst_ID, out_rst, fill=-99999, id_fld='sort_ID'):
    # Join fields from df to rst_ID to create new out_rst
    # replace null with fill
    # df.select_dtypes(exclude='object')
    trans_tbl = os.path.join(arcpy.env.workspace, os.path.basename(out_rst) + '_temp')
    DFtoTable(df, trans_tbl)
    arcpy.MakeTableView_management(trans_tbl, 'tableview')
    RemoveLayerFromMXD('rst_lyr') # in case of reprocessing
    arcpy.MakeRasterLayer_management(rst_ID, 'rst_lyr')
    arcpy.AddJoin_management('rst_lyr', 'Value', 'tableview', id_fld)
    arcpy.CopyRaster_management('rst_lyr', out_rst)
    return(out_rst)

def DFtoTable(df, tbl, fill=-99999):
    try:
        arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
    except ValueError:
        df.index.name = 'index'
        arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
    arcpy.Delete_management(tbl)
    arcpy.da.NumPyArrayToTable(arr, tbl)
    return(tbl)

def JoinDFtoRaster_setvalue(df, rst_ID, out_rst, fill=-99999, id_fld='sort_ID', val_fld=''):
    # Join fields from df to rst_ID to create new out_rst
    # replace null with fill
    # df.select_dtypes(exclude='object')
    # Convert DF to Table
    trans_tbl = os.path.join(arcpy.env.workspace, os.path.basename(out_rst) + '_temp')
    DFtoTable(df, trans_tbl)
    # trans_arr = df.select_dtypes(exclude=['object']).fillna(fill).to_records()
    # arcpy.Delete_management(trans_tbl)
    # arcpy.da.NumPyArrayToTable(trans_arr, trans_tbl)
    # Make raster
    RemoveLayerFromMXD('rst_lyr') # in case of reprocessing
    arcpy.MakeRasterLayer_management(rst_ID, 'rst_lyr')
    # Join data to raster and save as out_rst
    arcpy.MakeTableView_management(trans_tbl, 'tableview')
    arcpy.AddJoin_management('rst_lyr', 'Value', 'tableview', id_fld)
    # Try Lookup (FIXME: might require certain type of values, e.g. 'f8')
    if len(val_fld):
        try:
            # val_fld = os.path.basename(trans_tbl) + val_fld
            outRas = arcpy.sa.Lookup(out_rst, val_fld)
            outRas.save(out_rst+val_fld)
            print('New raster is saved as {}. Field "VALUE" is {}.'.format(out_rst+val_fld, val_fld))
        except:
            val_fld = ''
    if not len(val_fld):
        arcpy.CopyRaster_management('rst_lyr', out_rst)
        print('New raster is saved as {}. Field "VALUE" is ID and "UBW" is beachwidth.'.format(out_rst))
    return(out_rst)
