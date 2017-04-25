import arcpy, os, pythonaddins
sys.path.append(r"\\Mac\Home\Documents\scripting\TransectExtraction") # path to TransectExtraction module
from TransectExtraction import *

SiteYear_strings = {'site':'Forsythe',
                    'year':'2014',
                    'region':'NewJersey'}
arcpy.env.workspace= home= r'T:\Commons_DeepDive\DeepDive\{region}\{site}\{year}\{site}{year}.gdb'.format(**SiteYear_strings)


source_dir = r'\\Mac\Home\DATA\RawFiles\GeomorphNet'

source_dir = r'Y:\DATA\RawFiles\GeomorphNet'
arcpy.env.workspace = source_dir
dlowlist = arcpy.ListFiles('*.shp')

spatial_reference=arcpy.SpatialReference(26918)

for fname in dlowlist:
	arcpy.DefineProjection_management(fname,spatial_reference)


# Field mapping
fms = arcpy.FieldMappings()

# there is one field map for each desired output field
fm_1 = arcpy.FieldMap()
# Add an input field for each file to be merged
fm_1.addInputField(infile_1,fieldname)
fm_1.addInputField(infile_2,fieldname)

outfield = fm_1.outputField
outfield.name = fieldname
outfield.type = 'Double'
fm_1.outputField = outfield


for field in arcpy.ListFields(filelist[0]):
	if not field.type == 'OID':
		fieldname = field.name
		# there is one field map for each desired output field
		fm = arcpy.FieldMap()
		# Add an input field for each file to be merged
		for fname in filelist:
			fm.addInputField(filename,fieldname)
		outfield = fm.outputField
		#outfield.name = fieldname
		outfield.type = 'Double'
		fm.outputField = outfield
		fms.addFieldMap(fm)

arcpy.Merge_management(filelist,outfile,fms)


outfile = home+'\\{site}{year}_DLpts'.format(**SiteYear_strings)
arcpy.Merge_management(dlowlist,outfile)