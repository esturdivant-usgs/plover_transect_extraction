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
        if not fieldExists(fc, newfname):
            arcpy.AddField_management(fc, newfname, fieldtype)
            if verbose:
                print 'Added '+newfname+' field to '+fc
        return fc
    if type(fieldlist) is list or type(fieldlist) is tuple:
        for newfname in fieldlist:
            AddNewField(fc, newfname, fieldtype, verbose)
    else:
        AddNewField(fc, fieldlist, fieldtype, verbose)
    return fc

def DeleteExtraFields(inTable,keepfields=[]):
    fldsToDelete = [x.name for x in arcpy.ListFields(inTable) if not x.required] # list all fields that are not required in the FC (e.g. OID@)
    if keepfields:
        [fldsToDelete.remove(fldToKeep) for fldToKeep in keepfields] # remove keepfields from fldsToDelete
    if len(fldsToDelete):
        arcpy.DeleteField_management(inTable,fldsToDelete)
    return inTable

def DeleteTempFiles(wildcard='*_temp'):
    templist = arcpy.ListFeatureClasses(wildcard)
    for tempfile in templist:
        arcpy.Delete_management(tempfile)
    return templist

def RemoveLayerFromMXD(lyrname):
    mxd = arcpy.mapping.MapDocument('CURRENT')
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, lyrname, df):
            arcpy.mapping.RemoveLayer(df, lyr)
    return True

def newcoord(coords, dist):
    # Computes new coordinates x3,y3 at a specified distance along the prolongation of the line from x1,y1 to x2,y2
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
    for (new, old) in newoldfields.items():
        if not fieldExists(fc,new):
            #arcpy.DeleteField_management(fc,new)
            arcpy.AddField_management(fc,new,fieldtype)
        with arcpy.da.UpdateCursor(fc,[new, old]) as cursor:
            for row in cursor:
                row[0] = row[1]
                cursor.updateRow(row)
        if fieldExists(fc,old):
            try:
                arcpy.DeleteField_management(fc,old)
            except:
                print arcpy.GetMessage(2)
                pass
    return fc

def AddXYAttributes(fc,newfc,prefix,proj_code=26918):
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
    fieldlist = [prefix+'_Lat',prefix+'_Lon',prefix+'_easting',prefix+'_northing']
    AddNewFields(newfc, fieldlist)
    with arcpy.da.UpdateCursor(newfc,[prefix+'_Lon',prefix+'_Lat',"SHAPE@XY"],spatial_reference=arcpy.SpatialReference(4269)) as cursor:
        for row in cursor:
            x,y = row[cursor.fields.index("SHAPE@XY")]
            row[cursor.fields.index(prefix+'_Lon')] = x
            row[cursor.fields.index(prefix+'_Lat')] = y
            cursor.updateRow(row)
    with arcpy.da.UpdateCursor(newfc,[prefix+'_easting',prefix+'_northing',"SHAPE@XY"],spatial_reference=arcpy.SpatialReference(proj_code)) as cursor:
        for row in cursor:
            x,y = row[cursor.fields.index("SHAPE@XY")]
            row[cursor.fields.index(prefix+'_easting')] = x
            row[cursor.fields.index(prefix+'_northing')] = y
            cursor.updateRow(row)
    return newfc

def ReplaceValueInFC(fc,fields=[],oldvalue=-99999,newvalue=None):
    # Replace oldvalue with newvalue in fields in fc
    if len(fields) < 1:
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
    if len(fields) < 1:
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

def ExtendLine(fc,new_fc,distance,proj_code=26918):
    # From GIS stack exchange http://gis.stackexchange.com/questions/71645/a-tool-or-way-to-extend-line-by-specified-distance
    # layer must have map projection
    def accumulate(iterable):
        # accumulate([1,2,3,4,5]) --> 1 3 6 10 15 (Equivalent to itertools.accumulate() which isn't present in Python 2.7)
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
        arcpy.FeatureClassToFeatureClass_conversion(fc,arcpy.env.workspace,new_fc)
    # Will use OID to determine how to break up flat list of data by feature.
    coordinates = [[row[0], row[1]] for row in arcpy.da.SearchCursor(new_fc, ["OID@", "SHAPE@XY"], explode_to_points=True)]
    oid,vert = zip(*coordinates)
    # Construct list of numbers that mark the start of a new feature class by counting OIDs and accumulating the values.
    vertcounts = list(accumulate(collections.Counter(oid).values()))
    #Grab the last two vertices of each feature
    lastpoint = [point for x,point in enumerate(vert) if x+1 in vertcounts or x+2 in vertcounts]
    # Obtain list of tuples of new end coordinates by converting flat list of tuples to list of lists of tuples.
    distance = float(distance)
    newvert = [newcoord(y, distance) for y in zip(*[iter(lastpoint)]*2)]
    j = 0
    with arcpy.da.UpdateCursor(new_fc, "SHAPE@XY", explode_to_points=True) as cursor:
        for i,row in enumerate(cursor):
            if i+1 in vertcounts:
                row[0] = newvert[j]
                j+=1
                cursor.updateRow(row)
    return new_fc

def SpatialSort(in_fc,out_fc,sort_corner='LL',reverse_order=False, startcount=0, sortfield='sort_ID'):
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

def SortTransectsFromSortLines(in_fc, base_fc, sort_line_list, sortfield='trans_sort',sort_corner='LL'):
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
    """
    # alternative (more efficient?):
    # arcpy.SelectLayerByLocation_management('split_temp', "INTERSECT", ShorelinePts, '1 METERS', invert_spatial_relationship="INVERT")
    # arcpy.DeleteFeatures_management('split_temp')
    """
    arcpy.SelectLayerByLocation_management("split_temp","INTERSECT", shoreline_pts,'1 METERS')
    # count intersecting inlet lines
    arcpy.SpatialJoin_analysis('split_temp',inletLines,out_line,"JOIN_ONE_TO_ONE")
    ReplaceFields(shoreline_pts,{'ORIG_FID':'OID@'},'SHORT')
    ReplaceFields(out_line,{'ORIG_FID':'OID@'},'SHORT')
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

def RasterToLandPerimeter(in_raster,out_polygon,threshold,agg_dist='30 METERS',min_area='300 SquareMeters',min_hole_sz='300 SquareMeters',manualadditions=None):
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

def CombineShorelinePolygons(bndMTL,bndMHW,inletLines,ShorelinePts,bndpoly):
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

def NewBNDpoly(old_boundary,modifying_feature,new_bndpoly='boundary_poly',vertexdist='25 METERS',snapdist='25 METERS'):
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
"""
def JoinMetricsToTransects(transects,tempfile,fieldnamesdict):
    # Add fields from tempfile to transects
    for new in fieldnamesdict.keys():
        if fieldExists(transects,new):
            try:
                arcpy.DeleteField_management(transects,new)
            except:
                pass
    arcpy.JoinField_management(transects, "OBJECTID", tempfile, "FID_"+transects, fieldnamesdict.values())
    # Rename new fields
    for (new,old) in fieldnamesdict.items():
        try:
            arcpy.AlterField_management(transects,old,new,new)
        except:
            pass
    arcpy.Delete_management(os.path.join(home,tempfile))
    return transects
"""
def JoinFields(fc,sourcefile,joinfieldsdict,joinfields=['sort_ID']):
    # Add fields from sourcefile to fc; alter
    # If joinfieldsdict is a list/tuple instead of dictionary, convert.
    if type(joinfieldsdict) is list or type(joinfieldsdict) is tuple:
        joinlist = joinfieldsdict
        joinfieldsdict = {}
        for new in joinlist:
            joinfieldsdict[new] = new
    # Prepare target FC to receive join: remove new field if it exists and find name of old field
    for (new,old) in joinfieldsdict.items():
        # Remove new field from FC if it already exists
        if fieldExists(fc,new):
            try:
                arcpy.DeleteField_management(fc,new)
            except:
                pass
        # Search for fieldname matching 'old' field
        found = False # initialize 'found' as False; if old field exists, it is True
        if fieldExists(sourcefile,old):
            found = True
        else:
            # identify most similarly named field and replace in joinfieldsdict
            fieldlist = arcpy.ListFields(sourcefile,old+'*')
            if len(fieldlist) < 2:
                joinfieldsdict[new]=fieldlist[0].name
                found=True
            else:
                for f in fieldlist:
                    if f.name.endswith('_sm'):
                        joinfieldsdict[new]=f.name
                        found=True
        if not found:
            raise AttributeError("Field similar to {} was not found in {}.".format(old ,sourcefile))
    # Add [old] fields from sourcefile to FC
    oldfields = joinfieldsdict.values()
    if len(joinfields)==1:
        try:
            arcpy.JoinField_management(fc, joinfields, sourcefile, joinfields, oldfields)
        except RuntimeError:
            print(arcpy.GetMessages(2))
            print("joinfieldsdict.values: {}".format(oldfields))
            print("joinfields: {}".format(joinfields))
    elif len(joinfields)==2:
        arcpy.JoinField_management(fc, joinfields[0], sourcefile, joinfields[1], oldfields)
    else:
        print 'joinfield accepts either one or two values only.'
    # Rename new fields from old fields
    for (new,old) in joinfieldsdict.items():
        if not new == old:
            try:
                arcpy.AlterField_management(fc,old,new,new)
            except:
                pass
    #arcpy.Delete_management(os.path.join(arcpy.env.workspace,sourcefile))
    return fc

def ShorelinePtsToTransects(extendedTransects, shoreline, inPtsDict, transUIDfield, proj_code, pt2trans_disttolerance):
    shl2trans = 'SHL2trans'
    shlfields = ['SL_Lon','SL_Lat','SL_easting','SL_northing','Bslope']
    arcpy.Intersect_analysis((shoreline,extendedTransects), shl2trans+'_temp', output_type='POINT')
    AddXYAttributes(fc=shl2trans+'_temp',newfc=shl2trans,prefix='SL',proj_code=proj_code) # Add lat lon and x y fields to create SHL2trans
    # Add slope from ShorelinePts to shoreline intersection with transects (which replace the XY values from the original shoreline points)
    ReplaceFields(inPtsDict['ShorelinePts'],{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(shl2trans,inPtsDict['ShorelinePts'], 'join_temp','#','#','#',"CLOSEST",pt2trans_disttolerance) # create join_temp
    arcpy.JoinField_management(shl2trans,transUIDfield,'join_temp',transUIDfield,'slope') # join slope from join_temp (from ShorelinePts) with SHL2trans points
    arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
    arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')
    arcpy.DeleteField_management(extendedTransects,shlfields) #In case of reprocessing
    arcpy.JoinField_management(extendedTransects,transUIDfield,shl2trans,transUIDfield,shlfields)
    return extendedTransects

def AddFeaturePositionsToTransects(extendedTransects, inPtsDict,  shoreline, armorLines, transUIDfield, proj_code, pt2trans_disttolerance):
    # Shoreline
    ShorelinePtsToTransects(extendedTransects, shoreline, inPtsDict, transUIDfield, proj_code, pt2trans_disttolerance)
    # Armor
    tempfile = 'trans_temp'
    arm2trans = "arm2trans"
    armz = 'Arm_z'
    armorfields = ['Arm_Lon','Arm_Lat','Arm_easting','Arm_northing','Arm_z']
    if not arcpy.Exists(arm2trans):
        # Create armor points with XY and LatLon fields
        DeleteExtraFields(armorLines)
        arcpy.Intersect_analysis((armorLines,extendedTransects), tempfile, output_type='POINT')
        AddXYAttributes(tempfile,arm2trans,'Arm',proj_code)
        # Get elevation at points
        if arcpy.Exists(elevGrid_5m):
            arcpy.sa.ExtractMultiValuesToPoints(arm2trans,elevGrid_5m) # this produced a Background Processing error: temporary solution is to disable background processing in the Geoprocessing Options
            arcpy.AlterField_management(arm2trans,elevGrid_5m,armz,armz)
        else:
            arcpy.AddField_management(arm2trans,armz)
    # Join
    arcpy.DeleteField_management(extendedTransects, armorfields) #In case of reprocessing
    arcpy.JoinField_management(extendedTransects, transUIDfield, arm2trans, transUIDfield, armorfields)
    # How do I know which point will be encountered first? - don't want those in back to take the place of

    # Dunes
    dh2trans = "dh2trans"
    dhfields = {'DH_Lon':'lon', 'DH_Lat':'lat', 'DH_easting':'east', 'DH_northing':'north', 'DH_z':'dhigh_z'}
    BeachPointMetricsToTransects(extendedTransects, inPtsDict['dhPts'], dh2trans, dhfields, joinfields=[transUIDfield,transUIDfield], firsttime=True, tempfile=tempfile, tolerance=pt2trans_disttolerance)
    dl2trans = "dl2trans"
    dlfields = {'DL_Lon':'lon', 'DL_Lat':'lat', 'DL_easting':'east', 'DL_northing':'north', 'DL_z':'dlow_z'}
    BeachPointMetricsToTransects(extendedTransects, inPtsDict['dlPts'], dl2trans, dlfields, joinfields=[transUIDfield,transUIDfield], firsttime=True, tempfile=tempfile, tolerance=pt2trans_disttolerance)

    return extendedTransects

def BeachPointMetricsToTransects(transects, oldPts, newPts, fieldnamesdict,joinfields=['sort_ID'],firsttime=True, tempfile='trans_temp', tolerance='25 METERS'):
    # Save only points within 10m of transect and join beach point metrics to transects
    # 1. Create ID field and populate with OBJECTID
    # 2. Join nearest point within 10m to transect --> tempfile
    if firsttime:
        #PointsToTransOrder(transects,oldPts,newPts,tempfile)
        ReplaceFields(oldPts,{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(transects,oldPts, tempfile,'#','#','#',"CLOSEST",tolerance) # one-to-one # Error could result from different coordinate systems?
    if not arcpy.Exists(newPts):
        arcpy.MakeFeatureLayer_management(oldPts,oldPts+'_lyr')
        arcpy.AddJoin_management(oldPts+'_lyr',"ID", tempfile,"ID","KEEP_COMMON") # KEEP COMMON is the key to this whole thing - probably a better way to accomplish with SelectByLocation...
        arcpy.CopyFeatures_management(oldPts+'_lyr', newPts)
        #arcpy.RemoveJoin_management(oldPts+'_lyr')
    # Delete any fields with raw suffix to prevent confusion with lat lon east north fields that we want to use
    try:
        for fname in arcpy.ListFields(transects,'*_raw'):
            arcpy.DeleteField_management(transects,fname)
    except:
        pass
    JoinFields(transects,tempfile,fieldnamesdict,joinfields=joinfields)
    return transects

def CalculateBeachDistances(extendedTransects, maxDH, create_points=True):
    # Set fields that will be used to calculate beach width and store the results
    fieldlist = ['DL_z','DH_z','Arm_z',
                'DL_zMHW', 'DH_zMHW','Arm_zMHW',
                "DistDH", "DistDL", "DistArm",
                "SL_easting", "SL_northing",
                "DH_easting", "DH_northing",
                "DL_easting", "DL_northing",
                "Arm_easting", "Arm_northing"]
    beachWidth_fields = ['MLW_easting',
              'MLW_northing',
              'beach_h_MHW',
              'beachWidth_MHW',
              'beach_h_MLW',
              'beachWidth_MLW',
              'CP_easting','CP_northing', # Ben's label for easting and northing of dune point (DL,DH,or DArm) to be used for beachWidth and beach_h_MHW
              'CP_zMHW']
    distfields = ['DistDH','DistDL','DistArm'] # distance from shoreline
    # Add fields if they don't already exist
    AddNewFields(extendedTransects,fieldlist)
    #AddNewFields(baseName,'Source_beachwidth','TEXT')
    AddNewFields(extendedTransects, beachWidth_fields)
    # Calculate
    errorct = transectct = 0
    with arcpy.da.UpdateCursor(extendedTransects,'*') as cursor:
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
            sl_x = row[flist.index('SL_easting')]
            sl_y = row[flist.index('SL_northing')]
            try:
                row[flist.index('DistDH')] = hypot(sl_x - row[flist.index('DH_easting')], sl_y - row[flist.index('DH_northing')])
            except TypeError:
                pass
            try:
                row[flist.index('DistDL')] = hypot(sl_x - row[flist.index('DL_easting')], sl_y - row[flist.index('DL_northing')])
            except TypeError:
                pass
            try:
                row[flist.index('DistArm')] = hypot(sl_x - row[flist.index('Arm_easting')], sl_y - row[flist.index('Arm_northing')])
            except TypeError:
                pass
            # Find which of DL, DH, and Arm is closest to MHW and not Null (exclude DH if higher than maxDH)
            cp = FindNearestPointWithZvalue(row,flist,distfields,maxDH) # prefix of closest point metric
            if cp: # if closest point was found calculate beach width with that point, otherwise skip
                # Calculate beach width = Euclidean distance from dune (DL, DH, or Arm) to MHW and MLW
                # Set values from each row
                d_x = row[flist.index(cp+'_easting')]
                d_y = row[flist.index(cp+'_northing')]
                b_slope = row[flist.index('Bslope')]
                sl_x = row[flist.index('SL_easting')]
                sl_y = row[flist.index('SL_northing')]
                #beachWidth_MHW = CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y)
                mlw_x, mlw_y, beachWidth_MLW = CalcBeachWidth_MLW(oMLW,d_x,d_y,b_slope,sl_x,sl_y)
                beach_h_MHW = row[flist.index(cp+'_zMHW')]
                # update Row values
                row[flist.index('MLW_easting')] = mlw_x
                row[flist.index('MLW_northing')] = mlw_y
                row[flist.index('beach_h_MHW')] = beach_h_MHW
                row[flist.index('beachWidth_MHW')] = row[flist.index('Dist'+cp)]
                row[flist.index('beach_h_MLW')] = beach_h_MHW-oMLW
                row[flist.index('beachWidth_MLW')] = beachWidth_MLW
                #row[flist.index('Source_beachwidth')] = cp
                row[flist.index('CP_easting')] = row[flist.index(cp+'_easting')]
                row[flist.index('CP_northing')] = row[flist.index(cp+'_northing')]
                row[flist.index('CP_zMHW')] = row[flist.index(cp+'_zMHW')]
            else:
                errorct +=1
                pass
            cursor.updateRow(row)
    # Report
    print("Beach Width could not be calculated for {} out of {} transects.".format(errorct,transectct))
    # Create MLW and CP points for error checking
    if create_points:
        arcpy.MakeXYEventLayer_management(extendedTransects,'MLW_easting','MLW_northing',MLWpts+'_lyr',utmSR)
        arcpy.CopyFeatures_management(MLWpts+'_lyr',MLWpts)
        arcpy.MakeXYEventLayer_management(extendedTransects,'CP_easting','CP_northing',CPpts+'_lyr',utmSR)
        arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)
    # Return
    return extendedTransects

def dist2inlet(in_line, transUIDfield, xpts, coord_priority = "LOWER_LEFT"):
    # Assign variables
    route = "shore_{}_temp".format(coord_priority)
    distance_table = "dist2inlet_{}_temp".format(coord_priority)
    ReplaceFields(in_line,{'ORIG_FID':'OID@'},'SHORT') # make ORIG_FID field in shoreline if doesn't already exist
    arcpy.CreateRoutes_lr(in_line,"ORIG_FID",route,"LENGTH",coordinate_priority=coord_priority) # convert the shoreline to routes
    arcpy.LocateFeaturesAlongRoutes_lr(xpts, route, 'ORIG_FID', '1 Meters',distance_table,'RID POINT MEAS',distance_field='NO_DISTANCE') # Calculate distance from each transect to [LL] inlet
    arcpy.JoinField_management(xpts, transUIDfield, distance_table, transUIDfield, "MEAS") # Add distance to xpts
    return xpts

def Dist2Inlet(transects, in_line, transUIDfield='sort_ID', xpts='xpts_temp', two_directions = True):
    # Measure distance from inlet to each transect in both directions
    if not arcpy.Exists(xpts):
        arcpy.Intersect_analysis([transects,in_line],xpts,'ALL','1 METERS','POINT')
    # Convert shoreline to routes between where each transect crosses the shoreline
    dist2inlet(in_line, transUIDfield, xpts, coord_priority = "LOWER_LEFT")
    if fieldExists(in_line, 'Join_Count'):
        try:
            arcpy.MakeFeatureLayer_management(in_line,in_line+'_lyr','"Join_Count">1') # Only use sections that intersect two inlet lines
        except:
            two_directions = False
            pass
    else:
        print('Field "Join_Count" does not exist in {}. We will assume that each shoreline line is bounded by an inlet.'.format(in_line))
    if two_directions:
        dist2inlet(in_line+'_lyr', transUIDfield, xpts, coord_priority = "UPPER_RIGHT")
        # Save lowest *non-Null* distance value as Dist2Inlet
        with arcpy.da.UpdateCursor(xpts, ('MEAS', 'MEAS_1')) as cursor:
            for row in cursor:
                if isinstance(row[0],float) and isinstance(row[1],float):
                    row[0] = min(row[0], row[1])
                elif not isinstance(row[0],float):
                    row[0] = row[1]
                cursor.updateRow(row)
    try:
        arcpy.AlterField_management(xpts, 'MEAS', 'Dist2Inlet')
    except:
        arcpy.AddField_management(xpts,'Dist2Inlet','DOUBLE')
        with arcpy.da.UpdateCursor(xpts,['Dist2Inlet','MEAS']) as cursor:
            for row in cursor:
                cursor.updateRow([row[1],row[1]])
        pass
    arcpy.DeleteField_management(transects,'Dist2Inlet') # in case of reprocessing
    arcpy.JoinField_management(transects, transUIDfield, xpts, transUIDfield, 'Dist2Inlet')
    return transects

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
    if len(cps)>0:
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
    CPfields = ['CP_easting','CP_northing','CP_zMHW']
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
                row[cursor.fields.index('CP_easting')] = row[cursor.fields.index(cp+'_easting')]
                row[cursor.fields.index('CP_northing')] = row[cursor.fields.index(cp+'_northing')]
                row[cursor.fields.index('CP_zMHW')] = row[cursor.fields.index(cp+'_zMHW')]
            else:
                errorct +=1
                pass
    # Create closest points for error checking
    arcpy.MakeXYEventLayer_management(baseName,'CP_easting','CP_northing',CPpts+'_lyr',utmSR)
    arcpy.CopyFeatures_management(CPpts+'_lyr',CPpts)
    return CPpts

def CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y):
    # Calculate beach width based on dune and shoreline coordinates (meters)
    try:
        # 6 Calculate beach width = Euclidean distance from dune to MLW
        beachWidth_MHW = hypot(sl_x - d_x, sl_y - d_y)
        output = beachWidth_MHW
    except TypeError:
        output = None
    return output

def CalcBeachWidth_MLW(oMLW,d_x,d_y,b_slope,sl_x,sl_y):
    # Calculate beach width based on dune and shoreline projected coordinates (meters), beach slope, and MLW adjustment value
    try:
        # Calculate Euclidean distance between MHW and MLW based on slope and MLW adjustment
        MLWdist = abs(oMLW/b_slope) # 1/17: ADDED abs()
        # Find coordinates of MLW based on transect azimuth and MLWdist
        mlw_x, mlw_y = newcoord([(d_x,d_y),(sl_x,sl_y)],MLWdist)

        # 6 Calculate beach width = Euclidean distance from dune to MLW
        dx = mlw_x - d_x
        dy = mlw_y - d_y
        beachWidth_MLW = hypot(dx, dy)

        output = [mlw_x, mlw_y, beachWidth_MLW]
    except TypeError:
        output = [None, None, None]
    return output
"""
def CalcBeachWidthGeometry(MLW,dune_lon,dune_lat,beach_z,beach_slope,SL_Lon,SL_Lat):
    # Calculate beach width based on dune and shoreline coordinates, beach height and slope, and MLW adjustment value
    try:
        beach_h_MLW = beach_z - MLW # vert. distance from MLW to dune
        delta_xm_MLW = abs(beach_h_MLW/beach_slope) # Euclidean distance between dune and MLW # Bslope replaces sin of slope # Bslope was pulled in from shoreline points

        # 3 Convert chord distance to Angular distance along great circle (gc)
        mlwKM = delta_xm_MLW/1000
        r = 6371 # Radius of earth in meters
        delta_x_gc_MLW = d2 = 2 * asin(mlwKM/(2*r))

        # 4 Find Azimuth between dune and MHW shoreline
        dlon = radians(SL_Lon - dune_lon)
        dlat = radians(SL_Lat - dune_lat)
        lon1 = radians(dune_lon)
        lat1 = radians(dune_lat)
        lon2 = radians(SL_Lon)
        lat2 = radians(SL_Lat)

        x = sin(dlon) * cos(lat2)
        y = (cos(lat1) * sin(lat2)) - (sin(lat1) * cos(lat2) * cos(dlon))
        theta = atan2(x,y)
        if degrees(theta) < 0:
            azimuth_SL = degrees(theta)+360
        else:
            azimuth_SL = degrees(theta)
        phiR = radians(azimuth_SL)

        # 5 Calculate Position of MLW shoreline based on azimuth # Replace SL position with MLW position # SL is MHW so MHW is replaced by MLW through complex geometry calculations
        latMLW = lat2 = asin((sin(lat2) * cos(d2)) + (cos(lat2) * sin(d2) * cos(phiR)))
        lonMLW = lon2 = lon2 + atan2(sin(phiR)*sin(d2)*cos(lat2), cos(d2)-sin(lat2)*sin(latMLW))
        MLW_Lat = degrees(latMLW)
        MLW_Lon = degrees(lonMLW)

        # 6 Calculate beach width from dune to MLW shoreline
        dlon = radians(MLW_Lon - dune_lon)
        dlat = radians(MLW_Lat - dune_lat)
        a = (sin(dlat/2) * sin(dlat/2)) + (cos(lat1) * cos(lat2) * (sin(dlon/2) * sin(dlon/2)))
        c = 2 * atan2(sqrt(a), sqrt(1-a)) # Angular distance in radians
        dMLW = r * c  # Distance (m) between dune and MLW
        beachWidth_MLW = dMLW*1000

        output = [beach_h_MLW, delta_xm_MLW, azimuth_SL, MLW_Lat, MLW_Lon, beachWidth_MLW]
    except TypeError:
        output = [None, None, None, None, None, None]
    return output
"""
