## Import iPlover Sites from PostgreSQL DB
## Requires VPN connection to DOI network!!!!!!!!
import arcpy, time

############### ---> CHOOSE WISELY <--- #######################################
out_folder_path = r'Y:\space\USGS\iPlover\iPlover_PostgreSQL' # Local working directory...
usrn = 'rob' # PostgreSQL username
passw = '#raNsOMeR0' # PostgreSQL password 
############################################################################### 

arcpy.env.workspace = out_folder_path + '\\' + 'iPlover.gdb' # ... to store iPlover data (.gdb)
arcpy.env.overwriteOutput = True

if arcpy.Exists(arcpy.env.workspace): # Do you already have an iPlover geodatabase?
	pass
else: # If not create one
	print 'iPlover geodatabase does not exist, creating...'
	arcpy.CreateFileGDB_management(out_folder_path, "iPlover.gdb")

if arcpy.Exists(out_folder_path + '\\' + 'iPloverPostgreSQL.sde'): # Have you connected to the PostgreSQL DB before?
	print 'Connection to PostgreSQL already exists, skipping'
else: # If not, creating connection
	# PostgreSQL Inputs
	print 'Connecting to iPlover PostgreSQL Database...'
	dbName = 'iPloverPostgreSQL.sde' # The name of the database connection file ([anything].sde)
	database_platform = 'POSTGRESQL' # The DBMS platform that will be connected to
	instance = 'cidasdpdasiplvr.cr.usgs.gov' # The database server or instance to which you will connect
	account_authentication = 'DATABASE_AUTH' # Database authentication
	username = usrn
	password = passw
	save_user_pass = 'SAVE_USERNAME' # Save the user name and password in the connection file.
	database = 'iplover' # The name of the database that you will be connecting to.

	# Connect to iPlover PostgreSQL Database
	arcpy.CreateDatabaseConnection_management(out_folder_path,dbName,database_platform,instance,account_authentication,
												username,password,save_user_pass,database)

# Timestamp for filename
format = "%Y%m%d_%H%M%S"
date = time.strftime(format)
outName = 'iPlover_' + date + '_temp'
	
# Extract points from table
print 'Extracting points for %s' %date
arcpy.MakeXYEventLayer_management('Y:\space\USGS\iPlover\iPlover_PostgreSQL\iPloverPostgreSQL.sde\iplover.public.entries',
									'longitude','latitude',outName, "WGS 1984")

# Save as Feature Class
print 'Saving points'
arcpy.CopyFeatures_management(outName, outName.strip('_temp'))

# Delete temp
arcpy.Delete_management(outName)

count = arcpy.GetCount_management(outName.strip('_temp'))
print "New iplover dump has %s records" %count

print 'Process complete'