#!/usr/bin/perl
use strict;
use warnings;

my $path = shift @ARGV or die "usage: $0 metrics.tsv\n";
open my $fh, '<', $path or die "cannot open $path: $!";
my $header = <$fh>;
my %row;
while (<$fh>) {
    chomp;
    my @f = split /\t/;
    $row{$f[0]} = \@f;
}
close $fh;

sub rel_pct {
    my ($target, $candidate) = @_;
    return 100 * abs($candidate - $target) / $target;
}

print "target\tcandidate\tfile_distance_pct\ttext_distance_pct\tdyn_sum_distance_pct\tcharacteristic_mape_pct\tcomposite_pct\n";
for my $target_name (qw(product_board_product test_board_product)) {
    for my $candidate_name (qw(workspace_o2 workspace_os)) {
        my $t = $row{$target_name} or next;
        my $c = $row{$candidate_name} or next;
        my $file = rel_pct($t->[1], $c->[1]);
        my $text = rel_pct($t->[2], $c->[2]);
        my $dyn = rel_pct($t->[5], $c->[5]);
        my ($sum, $n) = (0, 0);
        for my $i (7 .. 11) {
            next if $t->[$i] eq 'NA' || $c->[$i] eq 'NA';
            $sum += rel_pct($t->[$i], $c->[$i]);
            $n++;
        }
        my $named = $n ? $sum / $n : 0;
        my $composite = ($file + $text + $dyn + $named) / 4;
        printf "%s\t%s\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n",
            $target_name, $candidate_name, $file, $text, $dyn, $named,
            $composite;
    }
}
