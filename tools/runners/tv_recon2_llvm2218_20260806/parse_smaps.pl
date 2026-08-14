#!/usr/bin/perl
use strict;
use warnings;

print "pid\tcomm\ttotal_private_dirty_kb\tmain_heap_private_dirty_kb\tarena_like_count\tarena_like_private_dirty_kb\theap_plus_arena_kb\theap_plus_arena_pct\n";

for my $path (@ARGV) {
    my ($pid, $comm) = $path =~ m{/([0-9]+)_(.+)\.smaps$};
    next unless defined $pid;
    $comm =~ s/_$//;

    open my $fh, '<', $path or die "cannot open $path: $!";
    my ($start, $end, $perms, $mapping_name, $private_dirty);
    my ($total_pd, $heap_pd, $arena_pd, $arena_count) = (0, 0, 0, 0);

    my $flush = sub {
        return unless defined $start;
        $total_pd += $private_dirty;
        if ($mapping_name eq '[heap]') {
            $heap_pd += $private_dirty;
        }
        my $length = $end - $start;
        if ($perms eq 'rw-p'
            && $mapping_name eq ''
            && $start % 0x100000 == 0
            && $length > 0
            && $length <= 0x100000) {
            $arena_count++;
            $arena_pd += $private_dirty;
        }
    };

    while (my $line = <$fh>) {
        if ($line =~ /^([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+([rwxps-]{4})\s+[0-9a-fA-F]+\s+\S+\s+\d+\s*(.*)$/) {
            $flush->();
            ($start, $end, $perms, $mapping_name) = (hex($1), hex($2), $3, $4);
            $private_dirty = 0;
        } elsif ($line =~ /^Private_Dirty:\s+(\d+)\s+kB/) {
            $private_dirty = $1;
        }
    }
    $flush->();
    close $fh;

    my $combined = $heap_pd + $arena_pd;
    my $pct = $total_pd ? sprintf('%.1f', 100 * $combined / $total_pd) : '0.0';
    print join("\t", $pid, $comm, $total_pd, $heap_pd, $arena_count,
               $arena_pd, $combined, $pct), "\n";
}
