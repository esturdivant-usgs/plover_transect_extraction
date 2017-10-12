# TE_functions_archive.py


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


def SortTransectsFromSortLines_v1(in_fc, base_fc, sort_line_list, sortfield='sort_ID',sort_corner='LL'):
    # in_fc = transects to be sorted
    # base_fc =
    try:
        arcpy.AddField_management(in_fc, sortfield, 'SHORT')
    except:
        pass
    # First run to initialize sorted transects (base_fc)
    sort_line = sort_line_list[0]
    arcpy.SelectLayerByLocation_management(in_fc, overlap_type='INTERSECT', select_features=sort_line)
    arcpy.Sort_management(in_fc, base_fc,[['Shape','ASCENDING']],sort_corner) # Sort from lower left - this
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
        arcpy.Append_management(out_fc, base_fc)
    return base_fc


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


def ShorelinePtsToTransects(extendedTransects, inPtsDict, IDfield, proj_code, disttolerance=25):
    # shl2trans = 'SHL2trans'
    # shlfields = ['SL_Lon','SL_Lat','SL_x','SL_y','Bslope']
    shoreline = inPtsDict['shoreline']
    ShorelinePts = inPtsDict['ShorelinePts']
    arcpy.Intersect_analysis((shoreline, extendedTransects), 'SHL2trans_temp', output_type='POINT')
    shl2trans, shlfields = AddXYAttributes('SHL2trans_temp', 'SHL2trans', 'SL', proj_code)
    shlfields.append('Bslope')
    # Add lat lon and x y fields to create SHL2trans
    # Add slope from ShorelinePts to shoreline intersection with transects (which replace the XY values from the original shoreline points)
    ReplaceFields(inPtsDict['ShorelinePts'],{'ID':'OID@'},'SINGLE')
    arcpy.SpatialJoin_analysis(shl2trans, inPtsDict['ShorelinePts'], 'join_temp','#','#','#',"CLOSEST", '{} METERS'.format(disttolerance)) # create join_temp
    arcpy.JoinField_management(shl2trans,IDfield,'join_temp',IDfield,'slope') # join slope from join_temp (from ShorelinePts) with SHL2trans points
    arcpy.DeleteField_management(shl2trans,'Bslope') #In case of reprocessing
    arcpy.AlterField_management(shl2trans,'slope','Bslope','Bslope')
    arcpy.DeleteField_management(extendedTransects, shlfields) #In case of reprocessing
    arcpy.JoinField_management(extendedTransects, IDfield, shl2trans, IDfield, shlfields)
    return extendedTransects



def ArmorLineToTransects(in_trans, armorLines, IDfield, proj_code, elevGrid_5m):
    arm2trans="arm2trans"
    armorfields = ['Arm_Lon','Arm_Lat','Arm_x','Arm_y','Arm_z']
    if not arcpy.Exists(armorLines):
        print('No armoring file found so we will proceed without armoring data. If shorefront tampering is present at this site, cancel the operations to digitize.')
        AddNewFields(in_trans, armorfields, fieldtype="DOUBLE")
        return(in_trans)
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
    return(in_trans)


def BeachPointMetricsToTransects(transects, oldPts, newPts, fieldnamesdict,joinfields=['sort_ID'], tempfile='trans_temp', tolerance='25 METERS'):
    # Save only points within 10m of transect and join beach point metrics to transects
    # 1. Create ID field and populate with OBJECTID
    # 2. Join nearest point within 10m to transect --> tempfile
    ReplaceFields(oldPts, {'ID': 'OID@'}, 'SINGLE')
    arcpy.SpatialJoin_analysis(transects, oldPts, tempfile, '#', '#', '#', "CLOSEST", tolerance) # one-to-one # Error could result from different coordinate systems?
    if not arcpy.Exists(newPts):
        # Create FC of nearest point within 25m of transect
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
    # FIXME: this could be performed mostly with PANDAS
    # Add Feature Positions To Transects, XYZ from DH, DL, & Arm points within 10m of transects
    # Requires DH, DL, and SHL points, NA transects
    startPart1 = time.clock()
    if not in_trans == out_fc:
        arcpy.FeatureClassToFeatureClass_conversion(in_trans, home, out_fc)
    # Shoreline
    print('Getting position (lat, lon, x, y, Bslope) of MHW for each transect...')
    ShorelinePtsToTransects(out_fc, inPtsDict, IDfield, proj_code, disttolerance)
    # Armor
    print('Getting position (lat, lon, x, y, z) of beach armoring for each transect...')
    ArmorLineToTransects(out_fc, inPtsDict['armorLines'], IDfield, proj_code, elevGrid_5m)
    # Dunes
    PointMetricsToTransects(out_fc, inPtsDict['dhPts'], "dh2trans", 'DH', IDfield, tolerance=disttolerance)
    PointMetricsToTransects(out_fc, inPtsDict['dlPts'], "dl2trans", 'DL', IDfield, tolerance=disttolerance)
    # Time report
    endPart1 = time.clock()
    duration = endPart1 - startPart1
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print "AddFeaturePositionsToTransects() completed in %dh:%dm:%fs" % (hours, minutes, seconds)
    return out_fc


def PointMetricsToTransects(transects, oldPts, tempfile, prefix, idfield='sort_ID', tolerance='25 METERS'):
    # Join nearest points within 10m to transect --> tempfile
    # Get fieldnames and create field mapping
    fmapdict = find_similar_fields(prefix, oldPts)
    fmapdict['idfield'] = idfield
    fmapdict['transects'] = transects
    fmapdict['oldPts'] = oldPts
    fmap = '{idfield} "{idfield}" true true false 2 Short 0 0 , First, #, {transects}, {idfield}, -1, -1;'\
    '{lon[dest]} "{lon[dest]}" true true false 8 Double 0 0 , First, #, {oldPts}, {lon[src]},-1,-1;'\
    '{lat[dest]} "{lat[dest]}" true true false 8 Double 0 0 , First, #, {oldPts}, {lat[src]} ,-1,-1;'\
    '{east[dest]} "{east[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {east[src]} ,-1,-1;'\
    '{north[dest]} "{north[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {north[src]} ,-1,-1;'\
    '{_z[dest]} "{_z[dest]}" true true false 8 Double 0 0 ,First,#, {oldPts}, {_z[src]},-1,-1'.format(**fmapdict)
    # Perform join to copy fields from closest points to transects
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

def find_PtAtTrans_v1(in_trans, in_pts, prefix, z_fld, z_pts, snaptoline_on=False, proximity=25):
    # for each transect, get nearest DHpt
    # This works, except only gets X and Y of nearest point, not Z or ID...
    # Get Multipoint geometry that includes all points with Z
    if not arcpy.Exists(z_pts):
        arcpy.FeatureTo3DByAttribute_3d(in_pts, z_pts+'_temp', z_fld)
        arcpy.Dissolve_management(z_pts+'_temp', z_pts,"tile", multi_part='MULTI_PART')
    pts_cursor = arcpy.da.SearchCursor(z_pts, ("SHAPE@"))
    pts = pts_cursor.next()[0] # PointGeometry?
    # Initialize df
    df = pd.DataFrame(columns=[tID_fld, prefix+'_x', prefix+'_y', prefix+'_z'])
    # Iterate through transects
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@", tID_fld)):
        transect = row[0]
        #FIXME: the points returned by intersect do not have Z
        near_pts = transect.buffer(proximity).intersect(pts, 1)
        shortest_dist = float(proximity)
        for ipt in near_pts:
            if transect.distanceTo(ipt) < shortest_dist:
                shortest_dist = transect.distanceTo(ipt)
                pt = ipt
        if snaptoline_on:
            nearest_pt = transect.snapToLine(nearest_pt) # optional snapToLine...
        newrow = {tID_fld:row[1], prefix+'_x':pt.X, prefix+'_y':pt.Y, prefix+'_z':pt.Z}
        # add to DF
        df = df.append(newrow, ignore_index=True)
    df.index = df[tID_fld]
    df.drop(tID_fld, axis=1, inplace=True)
    return(df)


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

def CalcBeachWidth_MHW(d_x,d_y,sl_x,sl_y):
    # Calculate beach width based on dune and shoreline coordinates (meters)
    try:
        # 6 Calculate beach width = Euclidean distance from dune to MHW
        bw_mhw =np.hypot(sl_x - d_x, sl_y - d_y)
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
        bw_mlw =np.hypot(mlw_x - d_x, mlw_y - d_y)
        #print('bw_mlw - Distance between dune and MLW: {}'.format(bw_mlw))
        output = [mlw_x, mlw_y, bw_mlw]
    except TypeError:
        output = [None, None, None]
    return output

def CalculateBeachDistances(in_trans, out_fc, maxDH, home, dMHW, oMLW, MLWpts, CPpts, create_points=True, skip_field_check=False):
    # Calculate distances (beach height, beach width, beach slope, max elevation)
    # Requires: transects with shoreline and dune position information
    # USE: polyline.snapToLine(in_pt) method on
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
            print("Field '{}' not present in transects file '{}'. We recommend running AddFeaturePositionsToTransects(extendedTrans, extendedTransects, inPts_dict,  shoreline, armorLines, id_fld, proj_code, pt2trans_disttolerance, home, elevGrid_5m)".format(missing_fields, in_trans))
            raise Exception
            return False
    # Copy in_trans to out_fc if the output will be different than the input
    if not in_trans == out_fc:
        arcpy.FeatureClassToFeatureClass_conversion(in_trans, home, out_fc)
    # Add fields if they don't already exist
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
                row[flist.index('DistDH')] =np.hypot(sl_x - row[flist.index('DH_x')], sl_y - row[flist.index('DH_y')])
            except TypeError:
                pass
            try:
                row[flist.index('DistDL')] =np.hypot(sl_x - row[flist.index('DL_x')], sl_y - row[flist.index('DL_y')])
            except TypeError:
                pass
            try:
                row[flist.index('DistArm')] =np.hypot(sl_x - row[flist.index('Arm_x')], sl_y - row[flist.index('Arm_y')])
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



def GetBarrierWidths(in_trans, barrierBoundary, shoreline, IDfield='sort_ID', temp_gdb=r'\\Mac\Home\Documents\ArcGIS\temp.gdb'):
    """
    Island width - total land (WidthLand), farthest sides (WidthFull), and segment (WidthPart)
    """
    start = time.clock()
    home = arcpy.env.workspace
    arcpy.env.workspace = temp_gdb
    out_clipped ='trans_clipped2isl'
    arcpy.Clip_analysis(os.path.join(home, in_trans), os.path.join(home, barrierBoundary), out_clipped) # ~30 seconds
    # WidthLand
    ReplaceFields(out_clipped, {'WidthLand':'SHAPE@LENGTH'})
    # WidthFull
    #arcpy.CreateRoutes_lr(extendedTransects,id_fld,"transroute_temp","LENGTH",ignore_gaps="NO_IGNORE") # for WidthFull
    # Create simplified line for full barrier width that ignores interior bays: verts_temp > trans_temp > length_temp
    arcpy.FeatureVerticesToPoints_management(out_clipped, "verts_temp", "BOTH_ENDS")  # creates verts_temp=start and end points of each clipped transect # ~20 seconds
    # ALTERNATIVE: add start_x, start_y, end_x, end_y to in_trans and then calculate Euclidean distance from array
    #arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xptsbarrier_temp',output_type='POINT') # ~40 seconds
    #arcpy.Intersect_analysis([extendedTransects,barrierBoundary],'xlinebarrier_temp',output_type='LINE') # ~30 seconds
    #arcpy.CreateRoutes_lr(extendedTransects,id_fld,"transroute_temp","LENGTH")
    # find farthest point to sl_x, sl_y => WidthFull and closest point => WidthPart
    # Clip transects with boundary polygon
    arcpy.PointsToLine_management("verts_temp", "trans_temp", IDfield) # creates trans_temp: clipped transects with single vertices # ~1 min
    arcpy.SimplifyLine_cartography("trans_temp", "length_temp", "POINT_REMOVE", ".01", "FLAG_ERRORS", "NO_KEEP") # creates length_temp: removes extraneous bends while preserving essential shape; adds InLine_FID and SimLnFlag; # ~2 min 20 seconds
    ReplaceFields("length_temp", {'WidthFull':'SHAPE@LENGTH'})
    # Join clipped transects with full barrier lines and transfer width value
    arcpy.JoinField_management(out_clipped, IDfield, "length_temp", IDfield, "WidthFull")
    # WidthPart
    # Calc WidthPart as length of the part of the clipped transect that intersects MHW_oceanside
    arcpy.MultipartToSinglepart_management(out_clipped,'singlepart_temp')
    ReplaceFields("singlepart_temp", {'WidthPart': 'SHAPE@LENGTH'})
    arcpy.SelectLayerByLocation_management('singlepart_temp', "INTERSECT", shoreline, '10 METERS')
    arcpy.JoinField_management(out_clipped, IDfield, "singlepart_temp", IDfield, "WidthPart")
    # Add fields to original file
    joinfields = ["WidthFull", "WidthLand", "WidthPart"]
    arcpy.DeleteField_management(os.path.join(home, in_trans), joinfields) # in case of reprocessing
    arcpy.JoinField_management(os.path.join(home, in_trans), IDfield, out_clipped, IDfield, joinfields)
    # Time report
    duration = time.clock() - start
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print "Barrier island widths completed in %dh:%dm:%fs" % (hours, minutes, seconds)
    return out_clipped

def calc_TransDistances(in_trans, trans_df, tID_fld='sort_ID', MHW=''):
    sl2dl = pd.Series(np.nan, index=trans_df.index, name='DistDL')
    sl2dh = pd.Series(np.nan, index=trans_df.index, name='DistDH')
    sl2arm = pd.Series(np.nan, index=trans_df.index, name='DistArm') # dtype will 'object'
    # for each transect, calculate the distance along the transect from the shoreline to DH, DL, and Arm
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = row[0]
        tID = row[1]
        tran = trans_df.ix[tID]
        if not np.isnan(tran.DL_x):
            ptDL = transect.snapToLine(arcpy.Point(tran['DL_x'], tran['DL_y']))
            sl2dl[tID] = np.hypot(tran['SL_x']- ptDL[0].X, tran['SL_y'] - ptDL[0].Y)
        if not np.isnan(tran.DH_x):
            ptDH = transect.snapToLine(arcpy.Point(tran['DH_x'], tran['DH_y']))
            sl2dh[tID] = np.hypot(tran['SL_x'] - ptDH[0].X, tran['SL_y'] - ptDH[0].Y)
        if not np.isnan(tran.Arm_x):
            ptArm = transect.snapToLine(arcpy.Point(tran['Arm_x'], tran['Arm_y']))
            sl2arm[tID] = np.hypot(tran['SL_x'] - ptArm[0].X, tran['SL_y'] - ptArm[0].Y)
    # Join new columns to DF
    trans_df = join_columns(trans_df, pd.DataFrame({'DistDH': sl2dh,
                                        'DistDL': sl2dl,
                                        'DistArm': sl2arm
                                        }, index=trans_df.index))
    if len(MHW):
        trans_df = adjust2mhw(trans_df, MHW)
    return(trans_df)


def calc_BeachWidth_v1(in_trans, trans_df, tID_fld='sort_ID'):
    # v3 (v1: arcpy, v2: pandas, v3: pandas with snapToLine() from arcpy)
    # To find dlow proxy, uses code written by Ben in Matlab and converted to pandas by Emily
    # Adds snapToLine() polyline geometry method from arcpy
    uBW = pd.Series(np.nan, index=trans_df.index, name='uBW')
    uBH = pd.Series(np.nan, index=trans_df.index, name='uBH')
    feat = pd.Series(np.nan, index=trans_df.index, name='ub_feat') # dtype will 'object'
    for row in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
        transect = row[0]
        tID = row[1]
        tran = trans_df.ix[tID]
        if not np.isnan(tran.DL_x):
            iDL = {'x':tran['DL_x'], 'y':tran['DL_y'],
                   'z':tran['DL_zmhw'], 'ub_feat':'DL'}
        elif tran.DH_zmhw <= maxDH:
            iDL = {'x':tran['DH_x'], 'y':tran['DH_y'],
                   'z':tran['DH_zmhw'], 'ub_feat':'DH'}
        elif not np.isnan(tran.Arm_x):
            iDL = {'x':tran['Arm_x'], 'y':tran['Arm_y'],
                   'z':tran['Arm_zmhw'], 'ub_feat':'Arm'}
        else: # If there is no DL equivalent, BW and BH = null
            uBW[tID] = uBH[tID] = np.nan
            continue
        ptDL = transect.snapToLine(arcpy.Point(iDL['x'], iDL['y']))
        # Get beach width
        uBW[tID] = np.hypot(tran['SL_x'] - ptDL[0].X, tran['SL_y'] - ptDL[0].Y)
        uBH[tID] = iDL['z']
        feat[tID] = iDL['ub_feat']
    # Add new uBW and uBH fields to trans_df
    bw_df = pd.concat([uBW, uBH, feat], axis=1)
    # pts_df = (pts_df.drop(pts_df.axes[1].intersection(bw_df.axes[1]), axis=1).join(bw_df, on=tID_fld, how='outer'))
    trans_df = join_columns(trans_df, bw_df)
    return(trans_df)


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
        try:  # Only use sections that intersect two (or more) inlet lines
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
    return(transects)

def measure_Dist2Inlet(shoreline, in_trans, tID_fld='sort_ID'):
    start = time.clock()
    df = pd.DataFrame(columns=[tID_fld, 'Dist2Inlet'])
    for row in arcpy.da.SearchCursor(shoreline, ("SHAPE@")):
        line = row[0]
        for trow in arcpy.da.SearchCursor(in_trans, ("SHAPE@",  tID_fld)):
            transect = trow[0]
            tID = trow[1]
            if not line.disjoint(transect): #line and transect overlap
                shoreseg = line.cut(transect)
                # check that shoreseg touches inlet line, only use segs that do.
                mindist = min(shoreseg[0].length, shoreseg[1].length)
                df = df.append({tID_fld:tID, 'Dist2Inlet':mindist}, ignore_index=True)
    df.index = df[tID_fld]
    df.drop(tID_fld, axis=1, inplace=True)
    print_duration(start)
    return(df)

def SplitTransectsToPoints(in_trans, out_pts, barrierBoundary, temp_gdb=r'\\Mac\Home\Documents\ArcGIS\temp.gdb'):
    # Split transects into segments
    #FIXME: After XTools divides dataset, run FC to numpy with explode to points?
    clippedtrans='tidytrans_clipped2island'
    input1 = os.path.join(temp_gdb, in_trans+'split1')
    output = os.path.join(temp_gdb, in_trans+'split2')
    if not arcpy.Exists(clippedtrans):
        arcpy.Clip_analysis(in_trans, barrierBoundary, clippedtrans)
    home = arcpy.env.workspace
    # Convert transects to 5m points: multi to single; split lines; segments to center points
    arcpy.MultipartToSinglepart_management(clippedtrans, input1)
    arcpy.ImportToolbox("C:/Program Files (x86)/XTools/XTools Pro/Toolbox/XTools Pro.tbx")
    arcpy.XToolsGP_SplitPolylines_xtp(input1, output,"INTO_SPECIFIED_SEGMENTS","5 Meters","10","#","#","ORIG_OID")
    arcpy.env.workspace = home #reset workspace - XTools changes default workspace for some reason
    # FCtoDF(output, xy=True) # get segment centroids (not vertices)
    arcpy.FeatureToPoint_management(output, out_pts)
    return out_pts

def CalculateDistances(transPts):
    with arcpy.da.UpdateCursor(transPts, "*") as cursor:
        for row in cursor:
            flist = cursor.fields
            try:
                seg_x = row[flist.index('seg_x')]
                SL_easting = row[flist.index('SL_x')]
                seg_y = row[flist.index('seg_y')]
                SL_northing = row[flist.index('SL_y')]
                dist2mhw =np.hypot(seg_x - SL_easting, seg_y - SL_northing)
                row[flist.index('Dist_Seg')] = dist2mhw
                try:
                    row[flist.index('Dist_MHWbay')] = row[flist.index('WidthPart')] - dist2mhw
                except TypeError:
                    pass
                try:
                    row[flist.index('DistSegDH')] = dist2mhw - row[flist.index('DistDH')]
                except TypeError:
                    pass
                try:
                    row[flist.index('DistSegDL')] = dist2mhw - row[flist.index('DistDL')]
                except TypeError:
                    pass
                try:
                    row[flist.index('DistSegArm')] = dist2mhw - row[flist.index('DistArm')]
                except TypeError:
                    pass
            except TypeError:
                pass
            try:
                cursor.updateRow(row)
            except RuntimeError as err:
                print(err)
                pass
    return transPts

def CalculatePointDistances(transPts_presort, extendedTransects='extendedTransects, which is not provided', id_fld='sort_ID'):
    # Calculate distance of point from shoreline and dunes (Dist_Seg, Dist_MHWbay, DistSegDH, DistSegDL, DistSegArm)
    # Add xy for each segment center point
    ReplaceFields(transPts_presort, {'seg_x': 'SHAPE@X', 'seg_y': 'SHAPE@Y'})
    # clipped_trans must have transdistfields
    transdistfields = ['DistDH', 'DistDL', 'DistArm', 'SL_x', 'SL_y', 'WidthPart']
    missing_fields = fieldsAbsent(transPts_presort, transdistfields)
    if missing_fields:
        print("Input is missing required fields: {}. \nAttempting to retrieve from {}".format(missing_fields, extendedTransects))
        arcpy.JoinField_management(transPts_presort, id_fld, extendedTransects, id_fld, missing_fields)
    # Add fields whose values will be calculated
    distfields = ['Dist_Seg', 'Dist_MHWbay', 'seg_x', 'seg_y',
                  'DistSegDH', 'DistSegDL', 'DistSegArm']
    AddNewFields(transPts_presort, distfields)
    # Calculate Euclidean distances
    CalculateDistances(transPts_presort)
    return transPts_presort

def SummarizePointElevation(transPts, extendedTransects, out_stats, id_fld):
    # save max and mean in out_stats table using Statistics_analysis
    arcpy.Statistics_analysis(transPts, out_stats, [['ptZmhw', 'MAX'], ['ptZmhw',
                              'MEAN'], ['ptZmhw', 'COUNT']], id_fld)
    # remove mean values if fewer than 80% of 5m points had elevation values
    # with arcpy.da.UpdateCursor(out_stats, ['*']) as cursor:
    for row in arcpy.da.UpdateCursor(out_stats, ['*']):
        count = row[cursor.fields.index('COUNT_ptZmhw')]
        if count is None:
            row[cursor.fields.index('MEAN_ptZmhw')] = None
            cursor.updateRow(row)
        elif count / row[cursor.fields.index('FREQUENCY')] <= 0.8:
            row[cursor.fields.index('MEAN_ptZmhw')] = None
            cursor.updateRow(row)
    # add mean and max fields to points FC using JoinField_management
    # very slow: over 1 hr (Forsythe: 1:53)
    arcpy.JoinField_management(transPts, id_fld, out_stats, id_fld,
                               ['MAX_ptZmhw', 'MEAN_ptZmhw'])
    try:
        arcpy.DeleteField_management(extendedTransects, ['MAX_ptZmhw', 'MEAN_ptZmhw'])
        arcpy.JoinField_management(extendedTransects, id_fld, out_stats,
                               id_fld, ['MAX_ptZmhw', 'MEAN_ptZmhw'])
    except:
        arcpy.JoinField_management(extendedTransects, id_fld, transPts,
                               id_fld, ['MAX_ptZmhw', 'MEAN_ptZmhw'])
    return(transPts)


def FCtoDF_var2(fc, fcfields=[], dffields=[], fill=-99999, explode_to_points=False, xfields=[], id_fld=False, verbose=True):
    # Convert FeatureClass to pandas.DataFrame with np.nan values
    # 1. Convert FC to Numpy array
    if not len(fcfields):
        fcfields = [f.name for f in arcpy.ListFields(fc)]
    if verbose:
        message = 'Converting feature class to array...'
        print(message)
    arr = arcpy.da.FeatureClassToNumPyArray(os.path.join(arcpy.env.workspace, fc), fcfields, null_value=fill, explode_to_points=explode_to_points)
    # 2. Convert array to dict
    if verbose:
        print('Converting array to dataframe...')
    if not len(dffields):
        dffields = list(arr.dtype.names)
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
    for col, ser in df.iteritems():
        ser.replace(fill, np.nan, inplace=True)
    if len(xfields) > 0:
        df.drop(xfields, axis=1, inplace=True, errors='ignore')
    return(df)


def join_with_dataframes(join_fc, target_fc, join_id, target_id, fields=False):
    # Use pandas to perform outer join join_fc and target_fc
    # target_fc must have a column that matched join_id
    # null values will be replaced with fills
    join_df = FCtoDF(join_fc, dffields=fields, id_fld=join_id)
    target_df = FCtoDF(target_fc, dffields=fields, id_fld=target_id)
    # Remove columns from target that are present in join, except join_id
    join_df = join_df.drop(join_id, axis=1)
    dup_cols = target_df.axes[1].intersection(join_df.axes[1])
    target_df = target_df.drop(dup_cols, axis=1)
    # Perform join
    pts_final = target_df.join(join_df, on=join_id, how='outer')
    return(pts_final)
