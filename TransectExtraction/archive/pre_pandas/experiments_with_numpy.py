
# Get sorted list of unique transUIDfield values
transUIDs = unique_values(tranSplitPts,transUIDfield)

# Use numpy to perform transect averaging:
results = []
transUIDs = numpy.unique(transPts_array[transUIDfield])
for UID in transUIDs:


# Use numpy to perform transect averaging:
from itertools import groupby
from operator import itemgetter

transPts_array = arcpy.da.TableToNumPyArray(tranSplitPts)
for groupByID, rows in groupby(transPts_array, key=itemgetter(transUIDfield)):
    position1, position2, counter = 0, 0, 0
    for row in rows:
        position1+=row[0]
        position2+=row[1]
        counter+=1
    result.append([position1/counter, position2/counter, groupByID])


out_stats = "avgZ_byTransect"
arcpy.Statistics_analysis(tranSplitPts,out_stats,
    [['PointZ_mhw','MAX'],['PointZ_mhw','MEAN'],['PointZ_mhw','COUNT']],transUIDfield)

with arcpy.da.UpdateCursor(out_stats,['*']) as cursor:
    for row in cursor:
        if row[cursor.fields.index('COUNT_PointZ_mhw')]/row[cursor.fields.index('FREQUENCY')] <= 0.8:
            row[cursor.fields.index('MEAN_PointZ_mhw')] = None
            cursor.updateRow(row)

transPts_array = arcpy.da.TableToNumPyArray(tranSplitPts,"*",null_value=fill)
stats_array = arcpy.da.TableToNumPyArray(out_stats,"*")
import numpy.lib.recfunctions
join = numpy.lib.recfunctions.join_by(transUIDfield, transPts_array, stats_array, jointype='outer')

out_fc = home+"\\pts_withMeanMaxZ"
arcpy.da.NumpyArrayToFeatureClass(join,out_fc,('seg_x','seg_y'),utmSR)

# Copied from https://arcpy.wordpress.com/2012/02/01/calculate-a-mean-value-from-a-field/
def calculate_mean_value(table, field):
    stats_table = r"in_memory\stats"
    arcpy.Statistics_analysis(table, stats_table, [[field, "MEAN"]])
    mean_field = "MEAN_{0}".format(field)
    cursor = arcpy.SearchCursor(stats_table, "", "", mean_field)
    row = cursor.next()
    mean_value = row.getValue(mean_field)
    del cursor
    return mean_value
# ^ Can be replaced by below, but can below specify only certain rows?


# Attempt to customize:
def ZbyTransect(table,Zfield,UIDfield,maxZ={},mean={}):
    query = "{} = {}".format(UIDfield,uid)
    na = arcpy.da.TableToNumPyArray(table, Zfield, query)
    maxZ[uid] = numpy.max(na[Zfield])
    if numpy.count_nonzero(~numpy.isnan(na[Zfield]))/na[Zfield].size <= 0.8:
        mean[uid] = None
    else:
        mean[uid] = numpy.nanmean(na[Zfield])
    return maxZ, mean

table = pts_elevslope
field = "PointZ_mhw"
mean = {}
maxZ = {}
transUIDs = unique_values(tranSplitPts,transUIDfield)
for uid in transUIDs: # also very slow. Longer than 30 minutes.
    maxZ, mean = ZbyTransect(table,Zfield,UIDfield,maxZ,mean)
# Add fields to FC
Z_fields = ['max_Z','mean_Z']
AddNewFields(tranSplitPts,Z_fields,fieldtype="DOUBLE", verbose=True)
with arcpy.da.UpdateCursor(tranSplitPts,[transUIDfield]+Z_fields) as cursor:
    for row in cursor:
        row[1] = maxZ[row[0]]
        row[2] = mean[row[0]]
        cursor.updateRow(row)
