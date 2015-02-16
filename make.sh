#dd if=/dev/zero of=$1 bs=512 count=32768
#dd if=/dev/zero of=$1 bs=512 count=65536
#dd if=/dev/zero of=$1 bs=512 count=98304
dd if=/dev/zero of=$1 bs=512 count=66585
mkdosfs -F 32 $1
