#!/bin/sh
# Read-only /proc and /sys probe. Output is streamed to host; no result files.
set -u
LC_ALL=C; export LC_ALL
proc_root=/proc
sys_root=/sys
targets='@TARGETS@'
program='
function die(message) { print "ERROR\t" message > "/dev/stderr"; exit 70 }
function hex(value, i,n,c) {
 n=0; value=tolower(value)
 for(i=1;i<=length(value);i++) {
  c=index("0123456789abcdef",substr(value,i,1))-1
  if(c<0) die("bad mapping address")
  n=n*16+c
 }
 return n
}
function readstat(pid, path,line,tail,a,n,r) {
 path=root "/" pid "/stat"; r=(getline line <path); close(path)
 if(r!=1) {
  if(system("test -e " path)==0) die("unreadable stat PID=" pid)
  return 0
 }
 if(line !~ /^[0-9]+ \(.*\) / || substr(line,1,index(line," ")-1)!=pid) die("malformed stat PID=" pid)
 tail=line; sub(/^.*\) /,"",tail); n=split(tail,a,/ +/)
 if(n<20 || a[7] !~ /^[0-9]+$/ || a[8] !~ /^[0-9]+$/ || a[10] !~ /^[0-9]+$/ || a[20] !~ /^[0-9]+$/)
  die("missing stat fields PID=" pid)
 comm=substr(line,index(line,"(")+1,length(line)-length(tail)-index(line,"(")-2)
 if(comm ~ /[\t\r\n]/) die("unsafe comm PID=" pid)
 state=a[1]; flags=a[7]+0; start=a[20]; minor=a[8]; major=a[10]
 return 1
}
function flushmap(kind,len,anon) {
 if(!have) return
 if(!dirty_seen) die("missing Private_Dirty PID=" current_pid)
 len=finish-begin
 anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
 if(name=="[heap]" || (perms=="rw-p" && name=="" && begin%1048576==0 && len>0 && len<=1048576)) g+=pd
 else if(substr(perms,2,1)=="w" && anon) o+=pd
 else f+=pd
 have=0; mappings++
}
function maps(pid, path,line,a,n,i,r) {
 path=root "/" pid "/smaps"; current_pid=pid
 g=0; o=0; f=0; have=0; mappings=0
 while((r=(getline line <path))>0) {
  if(line ~ /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-] /) {
   flushmap(); n=split(line,a,/ +/); split(a[1],addresses,"-")
   begin=hex(addresses[1]); finish=hex(addresses[2]); perms=a[2]
   name=""; for(i=6;i<=n;i++) name=name (i==6?"":" ") a[i]
   pd=0; dirty_seen=0; have=1
  } else if(line ~ /^Private_Dirty:/) {
   n=split(line,a,/ +/)
   if(!have || dirty_seen || n!=3 || a[2] !~ /^[0-9]+$/ || a[3]!="kB") die("bad Private_Dirty PID=" pid)
   pd=a[2]+0; dirty_seen=1
  }
 }
 close(path)
 if(r<0) return -1
 flushmap()
 return mappings
}
function globals(path,line,a,n,r,mem,used,found,orig,compr,zmem) {
 path=root "/meminfo"
 while((r=(getline line <path))>0) if(line ~ /^MemAvailable:/) {
  split(line,a,/ +/); if(a[2] !~ /^[0-9]+$/) die("bad MemAvailable"); mem=a[2]; found++
 }
 close(path); if(r<0 || found!=1) die("missing MemAvailable")
 path=sysroot "/block/zram0/mm_stat"; r=(getline line <path); close(path)
 if(r!=1 || split(line,a,/ +/)<3) die("zram unavailable, not zero")
 for(n=1;n<=3;n++) if(a[n] !~ /^[0-9]+$/) die("bad zram counter")
 orig=a[1]; compr=a[2]; zmem=a[3]
 path=root "/swaps"; r=(getline line <path)
 if(r!=1 || line !~ /^Filename[ \t]+Type[ \t]+Size[ \t]+Used[ \t]+Priority/) die("bad swaps header")
 used=0
 while((r=(getline line <path))>0) {
  gsub(/^[ \t]+|[ \t]+$/,"",line)
  n=split(line,a,/[ \t]+/)
  if(n!=5 || a[3] !~ /^[0-9]+$/ || a[4] !~ /^[0-9]+$/) die("bad swaps row")
  if(a[1] ~ /zram/) used+=a[4]
 }
 close(path); if(r<0) die("unreadable swaps")
 printf "G\t%s\t%s\t%s\t%.0f\t%s\t%s\t%s\n",sample,epoch,mem,used,orig,compr,zmem
}
BEGIN {
 if(root !~ /^\/[a-zA-Z0-9_./-]+$/) die("invalid proc path")
 if(mode=="globals") { globals(); exit }
 if(mode=="proc") {
  if(split(target,fields,":")!=3 || fields[1] !~ /^[A-Za-z][A-Za-z0-9_-]*$/ || fields[2] !~ /^[1-9][0-9]*$/ || fields[3] !~ /^[0-9]+$/)
   die("invalid target")
  pid=fields[2]
  if(!readstat(pid) || start!=fields[3]) die("target identity before read PID=" pid)
  if(maps(pid)<=0) die("empty or unreadable target smaps PID=" pid)
  if(!readstat(pid) || start!=fields[3]) die("target identity after read PID=" pid)
  printf "P\t%s\t%s\t%s\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%s\t%s\n",sample,epoch,fields[1],pid,start,g,o,f,g+o+f,minor,major
  exit
 }
 if(mode!="inventory") die("unknown mode")
 for(arg=1;arg<ARGC;arg++) {
  path=ARGV[arg]; pid=path; sub(/^.*\//,"",pid)
  if(pid !~ /^[1-9][0-9]*$/) continue
  if(!readstat(pid)) { print "X\t" pid "\texited before inventory"; continue }
  saved_start=start
  if(state=="Z" || int(flags/2097152)%2==1) { print "X\t" pid "\tkernel-or-zombie"; continue }
  count=maps(pid)
  if(!readstat(pid)) { print "X\t" pid "\texited during inventory"; continue }
  if(start!=saved_start) die("inventory identity changed PID=" pid)
  if(count<=0) die("empty or unreadable live smaps PID=" pid)
  printf "I\t%s\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%s\t%s\n",pid,comm,start,g,o,f,g+o+f,minor,major
 }
 exit
}'

case "${1:-}" in
 inventory) awk -v root="$proc_root" -v mode=inventory "$program" "$proc_root"/[0-9]*; exit $?;;
 proc) awk -v root="$proc_root" -v mode=proc -v sample=0 -v epoch=0 -v target="${2:-}" "$program"; exit $?;;
 globals) awk -v root="$proc_root" -v sysroot="$sys_root" -v mode=globals -v sample=0 -v epoch=0 "$program"; exit $?;;
 collect) ;;
 *) echo 'ERROR invalid probe mode' >&2; exit 64;;
esac

mono_ns() { awk '{printf "%.0f\n",$1*1000000000}' "$proc_root/uptime"; }
start=$(mono_ns) || exit 71
i=0
while [ "$i" -le 600 ]; do
 deadline=$((start+i*1000000000))
 now=$(mono_ns) || exit 71
 if [ "$now" -lt "$deadline" ]; then
  delay=$(awk -v n="$((deadline-now))" 'BEGIN {printf "%.9f",n/1000000000}')
  sleep "$delay" || exit 71
 fi
 began=$(mono_ns) || exit 71
 epoch=$(date +%s%N) || exit 71
 case "$epoch" in ''|*[!0-9]*) echo 'ERROR invalid nanosecond date' >&2; exit 71;; esac
 awk -v root="$proc_root" -v sysroot="$sys_root" -v mode=globals -v sample="$i" -v epoch="$epoch" "$program" &
 jobs="$!"
 for target in $targets; do
  awk -v root="$proc_root" -v mode=proc -v sample="$i" -v epoch="$epoch" -v target="$target" "$program" &
  jobs="$jobs $!"
 done
 bad=0
 for job in $jobs; do wait "$job" || bad=1; done
 ended=$(mono_ns) || exit 71
 printf 'T\t%s\t%s\t%s\t%s\n' "$i" "$began" "$ended" "$deadline"
 if [ "$bad" -ne 0 ]; then echo 'ERROR read child failed' >&2; exit 72; fi
 if [ "$ended" -ge "$((deadline+1000000000))" ]; then echo 'ERROR 1 s deadline missed' >&2; exit 73; fi
 i=$((i+1))
done
echo SAMPLING_DONE
