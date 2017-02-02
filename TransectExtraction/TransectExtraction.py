# Transect Extraction module
# possible categories: preprocess, create, calculate

import arcpy, time, os, pythonaddins, collections, numpy
from math import radians, cos, asin, sin, atan2, sqrt, degrees, hypot
from operator import add

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
        return False
    else:
        return mfields

def fieldExists(inFeatureClass, inFieldName):
    try:
        fieldList = arcpy.ListFields(os.path.join(arcpy.env.workspace,inFeatureClass))
    except:
        fieldList = arcpy.ListFields(inFeatureClass)
    for iField in fieldList:
        if iField.name.lower() == inFieldName.lower():
            return True
    return False

def CopyAndWipeFC(in_fc, out_fc):
    # Make copy of transects and manually fill the gaps. Then select all the new transect and run the next piece of code.
    arcpy.CopyFeatures_management(in_fc, out_fc)
    # Replace values of all new transects
    tranFields = []
    for f in arcpy.ListFields(out_fc):
        tranFields.append(f.name)
    with arcpy.da.UpdateCursor(out_fc, tranFields[2:]) as cursor:
        for row in cursor:
            cursor.updateRow([None] * len(row))
    return out_fc

def AddNewFields(fc,fieldlist,fieldtype="DOUBLE", verbose=True):
    # Add fields to FC if they do not already exist. New fields must all be the same type.
    def AddNewField(fc, newfname, fieldtype, verbose):
        # Add single new field
        if not fieldExists(fc, newfname):
            arcpy.AddField_management(fc, newfname, fieldtype)
            if verbose:
                print 'Added '+newfname+' field to '+fc
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
    templist = arcpy.ListFeatureClasses(wildcard)
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
    linelen = hypot(dx, dy) # distance between xy1 and xy2
    x3 = x2 + dx/linelen * dist
    y3 = y2 + dy/linelen * dist
    return x3, y3

#Computes new coordinates x3,y3 at a specified distance
#along the prolongation of the line from x1,y1 to x2,y2
def newcoord(coords, dist):
    (x1,y1),(x2,y2) = coords
    dx = x2 - x1
    dy = y2 - y1
    linelen = hypot(dx, dy)

    x3 = x2 + dx/linelen * dist
    y3 = y2 + dy/linelen * dist
    return x3, y3

def ReplaceFields(fc,newoldfields,fieldtype='DOUBLE'):
    # Use tokens to save geometry properties as attributes
    # E.g. newoldfields={'LENGTH':'SHAPE@LENGTH'}
    spatial_ref = arcpy.Describe(fc).spatialReference
    for (new, old) in newoldfields.items():
        if not fieldExists(fc,new):
            #arcpy.DeleteField_management(fc,new)
            arcpy.AddField_management(fc,new,fieldtype)
        with arcpy.da.UpdateCursor(fc,[new, old], spatial_reference=spatial_ref) as cursor:
            for row in cursor:
                cursor.updateRow([row[1], row[1]])
        if fieldExists(fc,old):
            try:
                arcpy.DeleteField_management(fc,old)
            except:
                print arcpy.GetMessage(2)
                pass
    return fc

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

def ReplaceValueInFC(fc,oldvalue=9999,newvalue=None, fields="*"):
    # Replace oldvalue with newvalue in fields in fc
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        fieldindex = range(len(cursor.fields))
        for row in cursor:
            for i in fieldindex:
                if row[i] == oldvalue:
                    row[i] = newvalue
            cursor.updateRow(row)
            # try:
            #     cursor.updateRow(row)
            # except RuntimeError:
            #     print(cursor.fields[i])
            #     print(row)
    return fc

def ReplaceValueInFC_v1(fc,fields=[],oldvalue=-99999,newvalue=None):
    # Replace oldvalue with newvalue in fields in fc
    if not len(fields):
        fs = arcpy.ListFields(fc)
        for f in fs:
            fields.append(f.name)
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            for i in range(len(fields)):
                if row[i] == oldvalue:
                    row[i] = newvalue
            cursor.updateRow(row)
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

def ExtendLine(fc, new_fc, distance, proj_code=26918):
    # From GIS stack exchange http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance
    # layer must have map projection
    def accumulate(iterable):
        # accumulate([1,2,3,4,5]) --> 1 3 6 10 15
        # (Equivalent to itertools.accumulate() - isn't in Python 2.7)
        it = iter(iterable)
        total = next(it)
        yield total
        for element in it:
            total = add(total, element)
            yield total
    # Project transects to UTM
    if not arcpy.Describe(fc).spatialReference.factoryCode == proj_code:
        print 'Projecting {} to UTM'.format(fc)
        arcpy.Project_management(fc, new_fc, arcpy.SpatialReference(proj_code))  # project to GCS
    else:
        print '{} is already projected in UTM.'.format(fc)
        arcpy.FeatureClassToFeatureClass_conversion(fc, arcpy.env.workspace,new_fc)
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
        for i,row in enumerate(cursor):
            if i+1 in vertcounts:
                row[0] = newvert[j]
                j+=1
                cursor.updateRow(row)
    return new_fc

def SpatialSort(in_fc, out_fc, sort_corner='LL', reverse_order=False, startcount=0, sortfield='sort_ID'):
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

def SpatialSort_v1(in_fc,out_fc,sort_corner='LL',sortfield='sort_ID'):
    arcpy.Sort_management(in_fc,out_fc,[['Shape','ASCENDING']],sort_corner) # Sort from lower left - this
    try:
        arcpy.AddField_management(out_fc,sortfield,'SHORT')
    except:
        pass
    with arcpy.da.UpdateCursor(out_fc,['OID@',sortfield]) as cursor:
        for row in cursor:
            cursor.updateRow([row[0],row[0]])
    return out_fc

def SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield='sort_ID',sort_corner='LL'):
    # in_fc = transects to be sorted
    # base_fc =
    try:
        arcpy.AddField_management(in_fc,sortfield,'SHORT')
    except:
        pass
    sort_line = sort_line_list[0]
    arcpy.SelectLayerByLocation_management(in_fc, overlap_type='INTERSECT', select_features=sort_line)
    arcpy.Sort_management(in_fc,base_fc,[['Shape','ASCENDING']],sort_corner) # Sort from lower left - this
    ct = 0
    with arcpy.da.UpdateCursor(base_fc,['OID@',sortfield]) as cursor:
        for row in cursor:
            ct+=1
            cursor.updateRow([row[0],row[0]])
    for sort_line in sort_line_list[1:]:
        arcpy.SelectLayerByLocation_management(in_fc, select_features=sort_line)
        new_ct = ct
        out_fc = 'sort{}'.format(new_ct)
        arcpy.Sort_management(in_fc,out_fc,[['Shape','ASCENDING']],sort_corner) # Sort from lower left - this
        with arcpy.da.UpdateCursor(out_fc,['OID@',sortfield]) as cursor:
            for row in cursor:
                ct+=1
                cursor.updateRow([row[0],row[0]+new_ct])
        arcpy.Append_management(out_fc,base_fc)
    return base_fc

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

def PreprocessTransects_v1(site,old_transects=False,distance=3000):
    # Old version that uses TRANSORDER to store sort information
    if not old_transects:
        old_transects = '{}_LTtransects'.format(site)
    new_transects = '{}_LTtrans_sort'.format(site)
    extTransects = '{}_extTrans'.format(site)

    # reset TRANSORDER
    arcpy.Sort_management(old_transects,new_transects,[['Shape','ASCENDING']],'LL') # Sort from lower left
    with arcpy.da.UpdateCursor(new_transects,['OID@','TransOrder']) as cursor:
        for row in cursor:
            cursor.updateRow([row[0],row[0]])
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

def CreateShoreBetweenInlets_v1(SLdelineator,inletLines,out_line,proj_code=26918):
    typeFC = arcpy.Describe(SLdelineator).shapeType
    if typeFC == "Point" or typeFC =='Multipoint':
        # Create shoreline from shoreline points and inlet lines
        arcpy.PointsToLine_management(SLdelineator, 'line_temp')
        SLdelineator = 'line_temp'
    # Ready layers for processing
    DeleteExtraFields(inletLines)
    DeleteExtraFields(SLdelineator)
    line_temp = ReProject(SLdelineator,SLdelineator+'_utm',proj_code)
    # Merge and then extend shoreline to inlet lines
    arcpy.Merge_management([line_temp,inletLines],'shore_temp')
    arcpy.ExtendLine_edit('shore_temp','500 Meters')
    # Eliminate extra lines, e.g. bayside, based on presence of SHLpts
    arcpy.Intersect_analysis([inletLines,'shore_temp'],'xpts_temp','ONLY_FID',output_type='POINT')
    arcpy.SplitLineAtPoint_management('shore_temp','xpts_temp','split_temp','1 Meters')
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", SLdelineator,'1 METERS')
    # count intersecting inlet lines
    arcpy.SpatialJoin_analysis('split_temp',inletLines,out_line,"JOIN_ONE_TO_ONE")
    ReplaceFields(SLdelineator,{'ORIG_FID':'OID@'},'SHORT')
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
    arcpy.Erase_analysis(union,split_temp,union_2) # Erase from union layer the selected shoreline area in split
    arcpy.Dissolve_management(union_2, bndpoly, multi_part='SINGLE_PART') # Dissolve all features in union_2 to single part polygons
    print 'Select extra features for deletion\nRecommended technique: select the polygon/s to keep and then Switch Selection\n'
    return bndpoly

def DEMtoFullShorelinePoly(elevGrid,prefix,MTL,MHW,inletLines,ShorelinePts):
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

def ShorelinePtsToTransects(extendedTransects, inPtsDict, IDfield, proj_code, pt2trans_disttolerance):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']
    shoreline = inPtsDict['shoreline']
    ShorelinePts = inPtsDict['ShorelinePts']
    arcpy.Intersect_analysis((shoreline,extendedTransects), 'SHL2trans_temp', output_type='POINT')
    shl2trans, shlfields = AddXYAttributes('SHL2trans_temp', 'SHL2trans', 'SL', proj_code)
    shlfields.append('Bslope')
    # Add lat lon and x y fields to create SHL2trans
    # Add slope from ShorelinePts to shoreline intersection with transects (which replace the XY values from the original shoreline points)
    ReplaceFields(inPtsDict['ShorelinePts'],{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(shl2trans,inPtsDict['ShorelinePts'], 'join_temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # create join_temp
    arcpy.JoinField_management(shl2trans,IDfield,'join_temp',IDfield,'slope') # join slope from join_temp (from ShorelinePts) with SHL2trans points
    arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
    arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')
    arcpy.DeleteField_management(extendedTransects, shlfields) #In case of reprocessing
    arcpy.JoinField_management(extendedTransects, IDfield, shl2trans, IDfield, shlfields)
    return extendedTransects

def ArmorLineToTransects(in_trans, armorLines, IDfield, proj_code, elevGrid_5m):
    arm2trans="arm2trans"
    if not arcpy.Exists(arm2trans):
        # Create armor points with XY and LatLon fields
        tempfile = arm2trans+"_temp"
        DeleteExtraFields(armorLines)
        arcpy.Intersect_analysis((armorLines, in_trans), tempfile, output_type='POINT')
        arm2trans, armorfields = AddXYAttributes(tempfile, arm2trans, 'Arm', proj_code)
        armorfields.append('Arm_z')
        AddNewFields(arm2trans, 'Arm_z', fieldtype="DOUBLE")
        # Get elevation at points
        print('Getting elevation of beach armoring by extracting elevation values to arm2trans points.')
        arcpy.sa.ExtractMultiValuesToPoints(arm2trans,[[elevGrid_5m, 'z_tmp']]) # this produced a Background Processing error: temporary solution is to disable background processing in the Geoprocessing Options
        with arcpy.da.UpdateCursor(arm2trans, ['Arm_z','z_tmp']) as cursor:
            for row in cursor:
                cursor.updateRow([row[1], row[1]])
    else:
        armorfields = ['Arm_Lon','Arm_Lat','Arm_x','Arm_y','Arm_z']
    # Join
    arcpy.DeleteField_management(in_trans, armorfields) #In case of reprocessing
    arcpy.JoinField_management(in_trans, IDfield, arm2trans, IDfield, armorfields)
    # How do I know which point will be encountered first? - don't want those in back to take the place of
    return in_trans

def PointMetricsToTransects(transects, oldPts, tempfile, prefix, idfield='sort_ID', tolerance='25 METERS'):
    # Join nearest points within 10m to transect --> tempfile
    fmapdict = {'lon': {'dest': prefix+'_Lon'},
                'lat': {'dest': prefix+'_Lat'},
                'east': {'dest': prefix+'_x'},
                'north': {'dest': prefix+'_y'},
                '_z': {'dest': prefix+'_z'}}
    for key in fmapdict:
        src = key
        if not fieldExists(oldPts, src):
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
        fmapdict[key]['src'] = src
    fmapdict['idfield'] = idfield
    fmapdict['transects'] = transects
    fmapdict['oldPts'] = oldPts
    fmap = '{idfield} "{idfield}" true true false 2 Short 0 0 , First, #, {transects}, {idfield}, -1, -1;'\
    '{lon[dest]} "{lon[dest]}" true true false 8 Double 0 0 , First, #, {oldPts}, {lon[src]},-1,-1;'\
    '{lat[dest]} "{lat[dest]}" true true false 8 Double 0 0 , First, #, {oldPts}, {lat[src]} ,-1,-1;'\
    '{east[dest]} "{east[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {east[src]} ,-1,-1;'\
    '{north[dest]} "{north[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {north[src]} ,-1,-1;'\
    '{_z[dest]} "{_z[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {_z[src]},-1,-1'.format(**fmapdict)
    arcpy.SpatialJoin_analysis(transects, oldPts, tempfile, 'JOIN_ONE_TO_ONE',
                               'KEEP_COMMON', fmap, "CLOSEST", tolerance) # one-to-one # Error could result from different coordinate systems?
    destfields = []
    for val in fmapdict.values():
        try:
            destfields.append(val['dest'])
        except:
            pass
    arcpy.DeleteField_management(transects, destfields)
    arcpy.JoinField_management(transects, idfield, tempfile, idfield, destfields)
    return transects

def BeachPointMetricsToTransects(transects, oldPts, newPts, fieldnamesdict,joinfields=['sort_ID'], tempfile='trans_temp', tolerance='25 METERS'):
    # Save only points within 10m of transect and join beach point metrics to transects
    # 1. Create ID field and populate with OBJECTID
    # 2. Join nearest point within 10m to transect --> tempfile
    ReplaceFields(oldPts, {'ID': 'OID@'}, 'SINGLE')
    arcpy.SpatialJoin_analysis(transects, oldPts, tempfile, '#', '#', '#', "CLOSEST", tolerance) # one-to-one # Error could result from different coordinate systems?
    if not arcpy.Exists(newPts):
        # I'm not sure why this step (creating points) is necessary
        arcpy.MakeFeatureLayer_management(oldPts, oldPts+'_lyr')
        arcpy.AddJoin_management(oldPts+'_lyr', "ID", tempfile, "ID", "KEEP_COMMON") # KEEP COMMON is the key to this whole thing - probably a better way to accomplish with SelectByLocation...
        arcpy.CopyFeatures_management(oldPts+'_lyr', newPts)
        #arcpy.RemoveJoin_management(oldPts+'_lyr')
    # Delete any fields with raw suffix to prevent confusion with lat lon east north fields that we want to use
    try:
        [arcpy.DeleteField_management(transects, fname) for fname in arcpy.ListFields(transects,'*_raw')]
    except:
        pass
    JoinFields(transects, tempfile, fieldnamesdict, joinfields=joinfields)
    return transects

def AddFeaturePositionsToTransects(in_trans, out_fc, inPtsDict, IDfield, proj_code, disttolerance, home, elevGrid_5m):
    # Add Feature Positions To Transects, XYZ from DH, DL, & Arm points within 10m of transects
    # Requires DH, DL, and SHL points, NA transects
    startPart1 = time.clock()
    tempfile = 'trans_temp'
    if not in_trans == out_fc:
        arcpy.FeatureClassToFeatureClass_conversion(in_trans, home, out_fc)
    # Shoreline
    print('Getting position (lat, lon, x, y, Bslope) of MHW for each transect...')
    ShorelinePtsToTransects(out_fc, inPtsDict, IDfield, proj_code, disttolerance)
    # Armor
    print('Getting position (lat, lon, x, y, z) of beach armoring for each transect...')
    ArmorLineToTransects(out_fc, inPtsDict['armorLines'], IDfield, proj_code, elevGrid_5m)
    # Dunes
    PointMetricsToTransects(out_fc, inPtsDict['dhPts'], "dh2trans", 'DH',
                                 IDfield, tolerance=disttolerance)
    PointMetricsToTransects(out_fc, inPtsDict['dlPts'], "dl2trans", 'DL',
                                 IDfield, tolerance=disttolerance)
    # Time report
    endPart1 = time.clock()
    duration = endPart1 - startPart1
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print "AddFeaturePositionsToTransects() completed in %dh:%dm:%fs" % (hours, minutes, seconds)
    return out_fc

# Part 4 functions
def FindFieldWithMinValue(row,cursorfields,fieldlist):
    # return list of prefixes sorted in ascending order of their values
    vdict = dict()
    for f in fieldlist:
        v = row[cursorfields.index(f)]
        if v == None:
            pass
        else:
            vdict[v] = f
    vsorted = sorted(vdict.items(), key=lambda x: (x is None, x)) # this doesn't work
    cps = []
    for i in range(len(vsorted)):
        cps.append(vsorted[i][1])
    return cps

def FindNearestPointWithZvalue(row,cursorfields,distance_fields=['DistDH','DistDL','DistArm'],maxDH=2.5):
    # return the prefix ('DL', 'DH', or 'Arm') of point with shortest distance to MHW (exclude DH if higher than maxDH)
    cps = FindFieldWithMinValue(row,cursorfields,distance_fields)
    cp=None
    if len(cps):
        i = 0
        while i < len(cps):
            cp = cps[i][4:]
            if (row[cursorfields.index(cp+'_zMHW')] is None): # or (cp == 'DH' and (row[dict1[cp+'_z']] > maxDH)):
                cp = None
                i+=1
            elif cp == 'DH' and (row[cursorfields.index(cp+'_zMHW')] > maxDH):
                cp = None
                i+=1
            else:
                i = len(cps)+1
    else:
        cp = None
    return cp

def CreatePointsFromCP(baseName,CPpts,utmSR):
    CPfields = ['CP_x','CP_y','CP_zMHW']
    # Add fields if don't already exist
    for newfname in CPfields:
        if not fieldExists(baseName, newfname):
            arcpy.AddField_management(baseName, newfname, "DOUBLE")
            print 'Added '+newfname+' field to '+baseName
    with arcpy.da.UpdateCursor(baseName,'*') as cursor:
        for row in cursor:
            transectct +=1
            # Find which of DL, DH, and Arm is closest to MLW and not Null (exclude DH if higher than maxDH)
            cp = row[cursor.fields.index('Source_beachwidth')] # prefix of closest point metric
            if cp: # if closest point was found calculate beach width with that point, otherwise skip
                # Add coordinates of closest point
                row[cursor.fields.index('CP_x')] = row[cursor.fields.index(cp+'_x')]
                row[cursor.fields.index('CP_y')] = row[cursor.fields.index(cp+'_y')]
                row[cursor.fields.index('CP_zMHW')] = row[cursor.fields.index(cp+'_zMHW')]
            else:
                errorct +=1
                pass
    # Create closest points for error checking
    arcpy.MakeXYEventLayer_management(baseName,'CP_x','CP_y',CPpts+'_lyr',utmSR)
    arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)
    return CPpts

def CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y):
    # Calculate beach width based on dune and shoreline coordinates (meters)
    try:
        # 6 Calculate beach width = Euclidean distance from dune to MHW
        bw_mhw = hypot(sl_x - d_x, sl_y - d_y)
    except TypeError:
        bw_mhw = None
    return bw_mhw

def CalcBeachWidth_MLW(oMLW, duneXY, b_slope, shoreXY):
    # Calculate beach width based on dune and shoreline projected coordinates (meters), beach slope, and MLW adjustment value
    d_x, d_y = duneXY
    sl_x, sl_y = shoreXY
    try:
        # Calculate Euclidean distance between MHW and MLW based on slope and MLW adjustment
        MLWdist = abs(oMLW/b_slope) # 1/17: ADDED abs()
        #print('MLWdist - Distance between MHW and MLW: {}'.format(MLWdist))
        # Find coordinates of MLW based on transect azimuth and MLWdist
        mlw_x, mlw_y = newcoord([duneXY, shoreXY], MLWdist)
        #print('bw_mhw - Distance between dune and MHW: {}'.format(bw_mhw))
        # 6 Calculate beach width = Euclidean distance from dune to MLW
        bw_mlw = hypot(mlw_x - d_x, mlw_y - d_y)
        #print('bw_mlw - Distance between dune and MLW: {}'.format(bw_mlw))
        output = [mlw_x, mlw_y, bw_mlw]
    except TypeError:
        output = [None, None, None]
    return output

def CalculateBeachDistances(in_trans, out_fc, maxDH, home, dMHW, oMLW, MLWpts, CPpts, create_points=True, skip_field_check=False):
    # Calculate distances (beach height, beach width, beach slope, max elevation)
    # Requires: transects with shoreline and dune position information
    startPart2 = time.clock()
    # Set fields that will be used to calculate beach width and store the results
    in_fields = ['DL_z','DH_z','Arm_z',"SL_x", "SL_y",
                "DH_x", "DH_y","DL_x", "DL_y", "Arm_x", "Arm_y"]
    # List fields to be created and populated
    out_fields1 = ['DL_zMHW', 'DH_zMHW','Arm_zMHW',
                "DistDH", "DistDL", "DistArm"]
    beachWidth_fields = ['bh_mhw', 'bw_mhw', 'bh_mlw', 'bw_mlw',
              'CP_x','CP_y', 'CP_zMHW','MLW_x', 'MLW_y']# Ben's label for easting and northing of dune point (DL,DH,or DArm) to be used for beachWidth and bh_mhw
    distfields = ['DistDH','DistDL','DistArm'] # distance from shoreline
    # Check for necessary fields
    if not skip_field_check:
        missing_fields = fieldsAbsent(in_trans, in_fields)
        if missing_fields:
            print("Field '{}' not present in transects file '{}'. We recommend running AddFeaturePositionsToTransects(extendedTrans, extendedTransects, inPts_dict,  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance, home, elevGrid_5m)".format(missing_fields, in_trans))
            raise Exception
            return False
    # Copy in_trans to out_fc if the output will be different than the input
    if not in_trans == out_fc:
        arcpy.FeatureClassToFeatureClass_conversion(in_trans, home, out_fc)
    # Add fields if they don't already exist
    print('Adding fields to {} as type Double if they do not already exist.'.format(out_fc))
    AddNewFields(out_fc, out_fields1 + beachWidth_fields)
    # Calculate
    print('Running data access UpdateCursor to calculate values for fields {}...'.format(out_fields1 + beachWidth_fields))
    errorct = transectct = 0
    with arcpy.da.UpdateCursor(out_fc,'*') as cursor:
        for row in cursor:
            flist = cursor.fields
            transectct +=1
            try:
                row[flist.index('DL_zMHW')] = row[flist.index('DL_z')] + dMHW
            except TypeError:
                pass
            try:
                row[flist.index('DH_zMHW')] = row[flist.index('DH_z')] + dMHW
            except TypeError:
                pass
            try:
                row[flist.index('Arm_zMHW')] = row[flist.index('Arm_z')] + dMHW
            except TypeError:
                pass
            # Calc DistDH and DistDL: distance from DH and DL to MHW (ShL_northing,ShL_easting)
            sl_x = row[flist.index('SL_x')]
            sl_y = row[flist.index('SL_y')]
            try:
                row[flist.index('DistDH')] = hypot(sl_x - row[flist.index('DH_x')], sl_y - row[flist.index('DH_y')])
            except TypeError:
                pass
            try:
                row[flist.index('DistDL')] = hypot(sl_x - row[flist.index('DL_x')], sl_y - row[flist.index('DL_y')])
            except TypeError:
                pass
            try:
                row[flist.index('DistArm')] = hypot(sl_x - row[flist.index('Arm_x')], sl_y - row[flist.index('Arm_y')])
            except TypeError:
                pass
            # Find which of DL, DH, and Arm is closest to MHW and not Null (exclude DH if higher than maxDH)
            cp = FindNearestPointWithZvalue(row,flist,distfields,maxDH) # prefix of closest point metric
            if cp: # if closest point was found calculate beach width with that point, otherwise skip
                # Calculate beach width = Euclidean distance from dune (DL, DH, or Arm) to MHW and MLW
                # Set values from each row
                d_x = row[flist.index(cp+'_x')]
                d_y = row[flist.index(cp+'_y')]
                b_slope = row[flist.index('Bslope')]
                sl_x = row[flist.index('SL_x')]
                sl_y = row[flist.index('SL_y')]
                #bw_mhw = CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y)
                #bw_mlw = bw_mhw + abs(oMLW/b_slope)
                mlw_x, mlw_y, bw_mlw = CalcBeachWidth_MLW(oMLW, (d_x, d_y), b_slope, (sl_x, sl_y))
                # update Row values
                row[flist.index('MLW_x')] = mlw_x
                row[flist.index('MLW_y')] = mlw_y
                bh_mhw = row[flist.index(cp+'_zMHW')]
                row[flist.index('bh_mhw')] = bh_mhw
                bw_mhw = row[flist.index('Dist'+cp)]
                row[flist.index('bw_mhw')] = bw_mhw
                row[flist.index('bh_mlw')] = bh_mhw + oMLW
                row[flist.index('bw_mlw')] = bw_mlw
                #row[flist.index('Source_beachwidth')] = cp
                row[flist.index('CP_x')] = row[flist.index(cp+'_x')]
                row[flist.index('CP_y')] = row[flist.index(cp+'_y')]
                row[flist.index('CP_zMHW')] = row[flist.index(cp+'_zMHW')]
            else:
                errorct +=1
                pass
            cursor.updateRow(row)
    # Report
    print("Top of beach could not be located for {} out of {} transects.".format(errorct,transectct))
    # Create MLW and CP points for error checking
    if create_points:
        spatial_ref = arcpy.Describe(out_fc).spatialReference
        arcpy.MakeXYEventLayer_management(out_fc,'MLW_x','MLW_y',MLWpts+'_lyr',spatial_ref)
        arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)
        if not arcpy.Exists(CPpts):
            arcpy.MakeXYEventLayer_management(out_fc,'CP_x','CP_y',CPpts+'_lyr',spatial_ref)
            arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)
    # Time report
    endPart2 = time.clock()
    duration = endPart2 - startPart2
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print("CalculateBeachDistances() completed in %dh:%dm:%fs" % (hours, minutes, seconds))
    # Return
    return out_fc

def dist2inlet(in_line, IDfield, xpts, coord_priority = "LOWER_LEFT"):
    # Assign variables
    route = "shore_{}_temp".format(coord_priority.lower())
    dist_tbl = "dist2inlet_{}_temp".format(coord_priority.lower())
    # Prep in_line
    ReplaceFields(in_line, {'ORIG_FID': 'OID@'}, 'SHORT')  # make ORIG_FID field in shoreline if doesn't already exist
    # Measure distance of each point along shoreline route
    arcpy.CreateRoutes_lr(in_line, "ORIG_FID", route, "LENGTH",
                          coordinate_priority=coord_priority)
    arcpy.LocateFeaturesAlongRoutes_lr(xpts, route, 'ORIG_FID', '1 Meters', dist_tbl, 'RID POINT MEAS', distance_field='NO_DISTANCE') # Calculate distance from each transect to [LL] inlet
    # Store distances in xpts
    arcpy.JoinField_management(xpts, IDfield, dist_tbl, IDfield, "MEAS")
    return xpts

def Dist2Inlet(transects, in_line, IDfield='sort_ID', xpts='xpts_temp', two_directions=True):
    # Measure distance from inlet to each transect in both directions
    startPart3 = time.clock()
    """
    Set up
    """
    if not arcpy.Exists(xpts): # Use shl2trans instead?
        arcpy.Intersect_analysis([transects, in_line], xpts, 'ALL', '1 METERS', 'POINT')
    else:
        arcpy.DeleteField_management(xpts, ['MEAS', 'MEAS_1'])
    """
    # Convert shoreline to routes between where each transect crosses the shoreline
    """
    print('Measuring distance to each transect from lower left corner')
    dist2inlet(in_line, IDfield, xpts, coord_priority = "LOWER_LEFT")
    """
    # Perform dist2inlet calculations from other direction on shoreline that is bounded by an inlet on both sides.
    """
    if fieldExists(in_line, 'SUM_Join_Count'):
        try:  # Only use sections that intersect two inlet lines
            arcpy.MakeFeatureLayer_management(in_line,in_line+'_lyr','"SUM_Join_Count">1')
            in_line = in_line+'_lyr'
        except:  # Fails if no features have join_count of more than 1
            two_directions = False
            pass
    else:
        print('Field "SUM_Join_Count" does not exist in {}. We will assume that each shoreline line is bounded by an inlet.'.format(in_line))
    if two_directions:
        print('Measuring distance from other corner (upper right)')
        dist2inlet(in_line, IDfield, xpts, coord_priority = "UPPER_RIGHT")
        # Save the smallest values from the two to MEAS
        with arcpy.da.UpdateCursor(xpts, ('MEAS', 'MEAS_1')) as cursor:
            for row in cursor:
                if isinstance(row[0],float) and isinstance(row[1],float):
                    row[0] = min(row[0], row[1])
                elif not isinstance(row[0],float):
                    row[0] = row[1]
                cursor.updateRow(row)
    # Convert MEAS to Dist2Inlet
    try:
        arcpy.AlterField_management(xpts, 'MEAS', 'Dist2Inlet') # Fails when Dist2Inlet field already exists.
    except:  # If field name won't change, do it manually:
        # Create Dist2Inlet field and copy values from MEAS. MEAS will be deleted later.
        arcpy.AddField_management(xpts,'Dist2Inlet','DOUBLE')
        with arcpy.da.UpdateCursor(xpts,['Dist2Inlet','MEAS']) as cursor:
            for row in cursor:
                cursor.updateRow([row[1],row[1]])
        pass
    # Join field Dist2Inlet
    arcpy.DeleteField_management(transects,'Dist2Inlet') # if reprocessing
    arcpy.JoinField_management(transects, IDfield, xpts, IDfield, 'Dist2Inlet')
    # Time report
    endPart3 = time.clock()
    duration = endPart3 - startPart3
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print "Dist2Inlet() completed in %dh:%dm:%fs" % (hours, minutes, seconds)
    return transects

def GetBarrierWidths(in_trans, barrierBoundary, shoreline, IDfield='sort_ID', clipped_trans='trans_clipped2island_temp'):
    """
    Island width - total land (WidthLand), farthest sides (WidthFull), and segment (WidthPart)
    """
    startPart4 = time.clock()
    # ALTERNATIVE: add start_x, start_y, end_x, end_y to baseName and then calculate Euclidean distance from array
    #arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xptsbarrier_temp',output_type='POINT') # ~40 seconds
    #arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xlinebarrier_temp',output_type='LINE') # ~30 seconds
    #arcpy.CreateRoutes_lr(extendedTransects,transUIDfield,"transroute_temp","LENGTH")
    # find farthest point to sl_x, sl_y => WidthFull and closest point => WidthPart
    # Clip transects with boundary polygon
    arcpy.Clip_analysis(in_trans, barrierBoundary, clipped_trans) # ~30 seconds
    # WidthLand
    ReplaceFields(clipped_trans,{'WidthLand':'SHAPE@LENGTH'})
    # WidthFull
    #arcpy.CreateRoutes_lr(extendedTransects,transUIDfield,"transroute_temp","LENGTH",ignore_gaps="NO_IGNORE") # for WidthFull
    # Create simplified line for full barrier width that ignores interior bays: verts_temp > trans_temp > length_temp
    arcpy.FeatureVerticesToPoints_management(clipped_trans, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect # ~20 seconds
    arcpy.PointsToLine_management("verts_temp","trans_temp",IDfield) # creates trans_temp: clipped transects with single vertices # ~1 min
    arcpy.SimplifyLine_cartography("trans_temp", "length_temp","POINT_REMOVE",".01","FLAG_ERRORS","NO_KEEP") # creates length_temp: removes extraneous bends while preserving essential shape; adds InLine_FID and SimLnFlag; # ~2 min 20 seconds
    ReplaceFields("length_temp",{'WidthFull':'SHAPE@LENGTH'})
    # Join clipped transects with full barrier lines and transfer width value
    arcpy.JoinField_management(clipped_trans, IDfield, "length_temp", IDfield, "WidthFull")

    # Calc WidthPart as length of the part of the clipped transect that intersects MHW_oceanside
    arcpy.MultipartToSinglepart_management(clipped_trans,'singlepart_temp')
    ReplaceFields("singlepart_temp", {'WidthPart': 'SHAPE@LENGTH'})
    arcpy.SelectLayerByLocation_management('singlepart_temp', "INTERSECT", shoreline, '10 METERS')
    arcpy.JoinField_management(clipped_trans, IDfield, "singlepart_temp", IDfield, "WidthPart")
    # Add fields to original file
    joinfields = ["WidthFull", "WidthLand", "WidthPart"]
    arcpy.DeleteField_management(in_trans, joinfields) # in case of reprocessing
    arcpy.JoinField_management(in_trans, IDfield, clipped_trans, IDfield, joinfields)
    # Time report
    endPart4 = time.clock()
    duration = endPart4 - startPart4
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print "Barrier island widths completed in %dh:%dm:%fs" % (hours, minutes, seconds)
    return clipped_trans

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
    # Convert feature class to continuous raster inwhich output raster has takes the values from the nearest feature (Euclidean distance).
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

def SplitTransectsToPoints(in_trans, out_pts, barrierBoundary, home, clippedtrans='tidytrans_clipped2island'):
    """
    # Split transects into segments
    """
    if not arcpy.Exists(clippedtrans):
        arcpy.Clip_analysis(in_trans, barrierBoundary, clippedtrans)
    # Convert transects to 5m points: multi to single; split lines; segments to center points
    #arcpy.MultipartToSinglepart_management(baseName, tranSplitPts+'Sing_temp')
    input1 = os.path.join(home,'singlepart_temp')
    output = os.path.join(home, 'singlepart_split_temp')
    arcpy.MultipartToSinglepart_management(clippedtrans, input1)
    arcpy.AddToolbox("C:/ArcGIS/XToolsPro/Toolbox/XTools Pro.tbx")
    arcpy.XToolsGP_SplitPolylines_xtp(input1,output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
    arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
    arcpy.FeatureToPoint_management(output, out_pts)
    return out_pts

def CalculatePointDistances(transPts_presort, extendedTransects):
    # Calculate distance of point from shoreline and dunes (Dist_Seg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
    # Add xy for each segment center point
    ReplaceFields(transPts_presort, {'seg_x': 'SHAPE@X', 'seg_y': 'SHAPE@Y'})
    # clipped_trans must have transdistfields
    transdistfields = ['DistDH', 'DistDL', 'DistArm', 'SL_x', 'SL_y', 'WidthPart']
    missing_fields = fieldsAbsent(transPts_presort, transdistfields)
    if missing_fields:
        print("Input is missing required fields: {}. \nAttempting to retrieve from {}".format(missing_fields, extendedTransects))
        arcpy.JoinField_management(transPts_presort, transUIDfield, extendedTransects, transUIDfield, missing_fields)
    # Add fields whose values will be calculated
    distfields = ['Dist_Seg', 'Dist_MHWbay', 'seg_x', 'seg_y',
                  'DistSegDH', 'DistSegDL', 'DistSegArm']
    AddNewFields(transPts_presort, distfields)
    # Calculate Euclidean distances
    with arcpy.da.UpdateCursor(transPts_presort, "*") as cursor:
        for row in cursor:
            flist = cursor.fields
            try:
                seg_x = row[flist.index('seg_x')]
                SL_easting = row[flist.index('SL_x')]
                seg_y = row[flist.index('seg_y')]
                SL_northing = row[flist.index('SL_y')]
                dist2mhw = hypot(seg_x - SL_easting, seg_y - SL_northing)
                row[flist.index('Dist_Seg')] = dist2mhw
                row[flist.index('Dist_MHWbay')] = row[flist.index('WidthPart')] - dist2mhw
                try:
                    row[flist.index('DistSegDH')] = dist2mhw-row[flist.index('DistDH')]
                except TypeError:
                    pass
                try:
                    row[flist.index('DistSegDL')] = dist2mhw-row[flist.index('DistDL')]
                except TypeError:
                    pass
                try:
                    row[flist.index('DistSegArm')] = dist2mhw-row[flist.index('DistArm')]
                except TypeError:
                    pass
            except TypeError:
                pass
            cursor.updateRow(row)
    return transPts_presort
