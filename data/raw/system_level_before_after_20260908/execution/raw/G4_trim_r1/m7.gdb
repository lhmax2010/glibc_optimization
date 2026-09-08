set $fp=(void*)fopen("/opt/usr/glibc_memopt/system_level_before_after_20260908/G4_trim_r1/malloc_info_pre.xml","w")
if $fp == 0
echo FAIL_NULL_FILE\n
detach
quit 1
end
set $mrc=(int)malloc_info(0,$fp)
set $crc=(int)fclose($fp)
if $mrc != 0 || $crc != 0
echo FAIL_M7_RETURN\n
detach
quit 1
end
detach
quit 0
