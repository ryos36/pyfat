from struct import unpack, pack
from os import SEEK_SET, path
from time import localtime
import array

class FAT(object):
	Version = "0.2"

	# Static constants used
	EOF_FAT12 = 0x00000ff8
	EOF_FAT16 = 0x0000fff8
	EOF_FAT32 = 0x0ffffff8
	# The size of a FAT directory entry
	DIRSIZE = 32

	class Type:
		FAT12 = 1
		FAT16 = 2
		FAT32 = 3
		exFAT = 4

	class Attribute:
		READONLY = 0x01
		HIDDEN = 0x02
		SYSTEM = 0x04
		LABEL = 0x08
		DIRECTORY = 0x10
		ARCHIVE = 0x20
		LONGNAME = READONLY | HIDDEN | SYSTEM | LABEL

	class FatalError(Exception):
		def __init__(self, msg):
			self.msg = msg
		def __str__(self):
			return "Fatal Error %s" % self.msg

	class FileNotFoundError(Exception):
		def __init__(self, path):
			self.path = path
		def __str__(self):
			return "The file or directory \"%s\" doesn't exist" % self.path

	def __init__(self, fd):
		self.fd = fd
		self.__start = fd.tell()
		self.info = self.__parse_bios_prameter_block()
		if self.info["sectors_per_fat"] == 0 :
			self.info.update(self.__parse_bios_prameter_block32())
		else:
			self.info.update(self.__parse_boot_sector16())

		self.__fat_start_offset = self.info["reserved_sector_count"] * self.info["byte_per_sector"]
		self.type, self.EOF, self.__num_clusters = self.__determine_type()

		self.__root_dir_offset = ((self.info["num_fats"] * self.info["sectors_per_fat"]) * self.info["byte_per_sector"]) + self.__fat_start_offset

		self.__data_start_offset = self.__root_dir_offset + (FAT.DIRSIZE * self.info["root_entry_count"])
		if type == FAT.Type.FAT32 :
			self.__root_dir_offset = self.cluster_to_offset(self.info["root_cluster"])

	def root_dir_offset(self):
		return self.__root_dir_offset

	def data_start_offset(self):
		return self.__data_start_offset

	def copy_fat(self):
		fat_n = self.info["num_fats"]

		self.fd.seek(self.__fat_start_offset, SEEK_SET)
		fat_data = self.fd.read(self.info["sectors_per_fat"] * self.info["byte_per_sector"])
		for fat_i in range(1, fat_n ):
			self.fd.write(fat_data)

	def __parse_bios_prameter_block(self):
		data = unpack("<3x8sHBHBHHBHHHLL", self.fd.read(36))
		return {
			"oem_name": data[0].strip(" "),
			"byte_per_sector": data[1],
			"sectors_per_cluster": data[2],
			"reserved_sector_count": data[3],
			"num_fats": data[4],
			"root_entry_count": data[5],
			"total_sectors": data[6] if data[6] != 0 else data[12],
			"media_descriptor": data[7],
			"sectors_per_fat": data[8],
			"sectors_per_track": data[9],
			"num_heads": data[10],
			"hidden_sectors": data[11]
		}

	def __parse_bios_prameter_block32(self):
		data = unpack("<LHHLHH12xBxBL11s8s", self.fd.read(54))
		return {
			"sectors_per_fat": data[0],
			"ext_flags" : data[1],
			"fsver" : data[2],
			"root_cluster" : data[3],
			"fsinfo" : data[4],
			"backup_boot_sec" : data[5],
			"drive_num" : data[6],
			"boot_signature" : data[7],
			"volume_id" : data[8],
			"volume_label" : data[9],
			"boot_file_system_type" : data[10]
		}

	def __parse_boot_sector16(self):
		data = unpack("<BxBL11s8s", self.fd.read(26))
		return {
			"drive_num" : data[0],
			"boot_signature" : data[1],
			"volume_id" : data[2],
			"volume_label" : data[3],
			"boot_file_system_type" : data[4]
		}

	def __check_max_cluster(self, cluster):
		if type == FAT.Type.FAT12 :
			return cluster < 4085

		if type == FAT.Type.FAT16 :
			return cluster < 65525

		return True
		
	# Determines which type of FAT it is depending on the properties
	def __determine_type(self):
		root_dir_sectors = ((self.info["root_entry_count"] * FAT.DIRSIZE) + (self.info["byte_per_sector"] - 1)) / self.info["byte_per_sector"]
		data_sectors = self.info["total_sectors"] - (self.info["reserved_sector_count"] + (self.info["num_fats"] * self.info["sectors_per_fat"]) + root_dir_sectors)
		num_clusters = data_sectors / self.info["sectors_per_cluster"]
		if num_clusters < 4085:
			return (FAT.Type.FAT12, FAT.EOF_FAT12, num_clusters)
		elif num_clusters < 65525:
			return (FAT.Type.FAT16, FAT.EOF_FAT16, num_clusters)
		else:
			return (FAT.Type.FAT32, FAT.EOF_FAT32, num_clusters)

	# Calculate the logical sector number from the cluster
	def cluster_to_offset(self, cluster):
		offset = ((cluster - 2) * self.info["sectors_per_cluster"]) * self.info["byte_per_sector"]
		return self.__data_start_offset + offset

	def __update_fs_info(self, clusters, last_cluster):
		if self.type != FAT.Type.FAT32 :
			return
		offset = self.info["fsinfo"] * self.info["byte_per_sector"]
		self.fd.seek(offset, SEEK_SET)
		data = unpack("<L480xLLL12xL", self.fd.read(512))
		if data[0] != 0x41615252 :
			return
		if data[1] != 0x61417272 :
			return
		if data[4] != 0xAA550000 :
			return
		self.fd.seek(offset + 488, SEEK_SET)
		data = pack("<LL", data[2] - clusters, last_cluster)
		self.fd.write(data)
		self.fd.seek(offset, SEEK_SET)
		data = unpack("<L480xLLL12xL", self.fd.read(512))

	def __flatten(self, lst, rv = None):
		if not rv :
			rv = []
		for i in lst:
			if isinstance(i, list):
				self.__flatten(i, rv)
			else:
				rv.append(i)
		return rv

	def __eval_checksum(self, short_name11) :
		sum = 0
		for c in short_name11:
			sum = (((sum & 0xFE)>> 1) + ((sum & 0x01) << 7) + ord(c)) & 0xFF
		return sum
		
	def __write_lfn(self, long_file_name_array, index, checksum) :
		if not long_file_name_array:
			return

		b0 = self.__flatten(
			(index,
			 long_file_name_array[0:5],
			 FAT.Attribute.LONGNAME,
			 0,
			 checksum,
			 long_file_name_array[5:11],
			 0,
			 long_file_name_array[11:13]))

		data = pack("<B5HBBB6HH2H", *b0)
		self.fd.write(data)
		#print "unpack:", unpack("<32B", data)
		self.__write_lfn(long_file_name_array[13:], (index & 0x3f) - 1, checksum)

	def __make_dir_entry(self, short_name11, create_time, start_cluster, file_size) :
		if not self.__check_max_cluster(start_cluster):
			raise FAT.FatalError

		str_time= localtime(create_time)
		wrt_date = (((str_time.tm_year - 1980) & 0x7F) << 9) | (str_time.tm_mon) << 5 | (str_time.tm_mday)
		wrt_time = ((str_time.tm_hour) << 11) | (str_time.tm_min) << 5 | (str_time.tm_sec / 2 )
		
		dir_data = pack("<11sBBBHHHHHHHL", short_name11, 
			FAT.Attribute.ARCHIVE,
			0,
			0,
			wrt_time,
			wrt_date,
			wrt_date,
			start_cluster / 0x10000,
			wrt_time,
			wrt_date,
			start_cluster % 0x10000,
			file_size)

		return dir_data

	def write_vfat(self, file_path, long_file_name, short_name, dir_offset, data_offset, fat_pos) :
		b0 = map(ord, long_file_name)
		b0.append(0)
		l = len(b0)
		l13 = ( l + 12 ) / 13 * 13
		#print b0, l, l13
		for v in range(l, l13):
			b0.append(0xffff)

		b1 = []
		ll = len(b0)/13
		for i in range(0, ll):
			l0 = ll - i -1
			#print l0 * 13, (l0  + 1) * 13
			b1.extend(b0[l0 * 13:(l0 + 1)*13])
		b0 = b1
			
		if short_name.find(".") < 0 :
			basename = short_name
			extension = "   "
		else :
			basename, extension = short_name.split(".")

		for i in range(len(basename), 8):
			basename += (" ")
		for i in range(len(extension), 3):
			extension += (" ")

		#print "\"" + basename + "\"" +  extension + "\""
		short_name11 = basename + extension
		checksum = self.__eval_checksum(short_name11)

		self.fd.seek(dir_offset, SEEK_SET)

		self.__write_lfn(b0, 0x40 + l13 / 13, checksum)
		b1 = b0[5:11]
		data = pack("<13H", *b0[0:13])

		file_size = path.getsize(file_path)
		cluster_bytes = self.info["byte_per_sector"] * self.info["sectors_per_cluster"]
		file_size_roundup = (file_size + cluster_bytes - 1) & ~(cluster_bytes - 1)
		file_size_clusters = file_size_roundup / cluster_bytes

		#print "file_size:", file_size, path.getctime(file_path)
		dir_data = self.__make_dir_entry(short_name11, path.getctime(file_path), fat_pos, file_size) 

		#print "dir_entry:", len(dir_data)
		#print "dir_entry:", type(dir_data)
		#print "dir_entry:", unpack("<32B", dir_data)

		self.fd.write(dir_data)
		dir_offset += l13 / 13 * FAT.DIRSIZE + len(dir_data)

		self.fd.seek(data_offset, SEEK_SET)
		with open(file_path, "rb") as f:
			for i in range(0, file_size_clusters):
				self.fd.write(f.read(cluster_bytes))

		data_offset += file_size_roundup

		self.fd.seek(self.__fat_start_offset + fat_pos * 4, SEEK_SET)
		#print 4 + ((file_size + 511)/512)
		for i in range(fat_pos, fat_pos + file_size_clusters - 1):
			self.fd.write(pack("<L", i + 1))
		#self.fd.write(pack("<L", 0x0fffffff))
		self.fd.write(pack("<L", self.EOF))

		fat_pos += file_size_clusters
		self.__update_fs_info(file_size_clusters, fat_pos - 1)

		return (dir_offset, data_offset, fat_pos) 
		
