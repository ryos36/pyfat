#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from fat import FAT
from sys import argv
from struct import unpack, pack

def main():
	argc = len(argv)
	fat = FAT(open(argv[1], "r+b"))
	#print fat
	if argc >= 3 :
		path = argv[2]

	#print fat.type
	#print fat32.info

	dir_offset = fat.root_dir_offset()
	data_offset = fat.data_start_offset() + 512
	fat_pos = 3

	print "0:", dir_offset, data_offset, fat_pos

	file_path = "sdcard/boot.bin"
	long_file_name = "boot.bin"
	short_name = "BOOT.BIN"

	dir_offset, data_offset, fat_pos = fat.write_vfat(file_path, long_file_name, short_name, dir_offset, data_offset, fat_pos) 
	print "1:", dir_offset, data_offset, fat_pos

	file_path = "sdcard/uramdisk.image.gz"
	long_file_name = "uramdisk.image.gz"
	short_name = "URAMDI~1.GZ"
	dir_offset, data_offset, fat_pos = fat.write_vfat(file_path, long_file_name, short_name, dir_offset, data_offset, fat_pos) 

	print "2:", dir_offset, data_offset, fat_pos

	file_path = "sdcard/devicetree.dtb"
	long_file_name = "devicetree.dtb"
	short_name = "DEVICE~1.DTB"
	dir_offset, data_offset, fat_pos = fat.write_vfat(file_path, long_file_name, short_name, dir_offset, data_offset, fat_pos) 

	print "3:", dir_offset, data_offset, fat_pos
	file_path = "sdcard/uImage"
	long_file_name = "uImage"
	short_name = "uImage"
	dir_offset, data_offset, fat_pos = fat.write_vfat(file_path, long_file_name, short_name, dir_offset, data_offset, fat_pos) 

	print "4:", dir_offset, data_offset, fat_pos

	fat.copy_fat()

	return(0)

if __name__ == "__main__":
	exit(main())

