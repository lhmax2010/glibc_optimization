Name:           glibc-memopt-tools
Version:        1.0.0
Release:        1
Summary:        Reproduction tools for gated glibc trim experiments
Group:          Development/Tools
License:        Proprietary
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  clang
BuildRequires:  pkg-config
BuildRequires:  glibc-devel
BuildRequires:  glib2-devel
BuildRequires:  gstreamer-devel

%description
Host-built ARM tools used to reproduce the alloc_bench, GStreamer loop-release,
and mapping-classification measurements documented by this repository.

%prep
%setup -q

%build
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1788364800}
COMMON_FLAGS="$CFLAGS -std=c99 -Wall -Wextra -Werror -fdebug-prefix-map=%{_builddir}/%{name}-%{version}=."
$CC $COMMON_FLAGS -D_GNU_SOURCE -pthread \
    -o alloc_bench tools/alloc_bench/alloc_bench.c
$CC $COMMON_FLAGS \
    -o reclaim_probe tools/reclaim_probe/reclaim_probe.c
$CC $COMMON_FLAGS $(pkg-config --cflags gstreamer-1.0 glib-2.0) \
    -o gst_loop_decode tools/gst_loop_decode/gst_loop_decode.c \
    $(pkg-config --libs gstreamer-1.0 glib-2.0) -pthread

%install
rm -rf %{buildroot}
install -d %{buildroot}%{_bindir}
install -m 0755 alloc_bench %{buildroot}%{_bindir}/alloc_bench
install -m 0755 gst_loop_decode %{buildroot}%{_bindir}/gst_loop_decode
install -m 0755 reclaim_probe %{buildroot}%{_bindir}/reclaim_probe

%files
%{_bindir}/alloc_bench
%{_bindir}/gst_loop_decode
%{_bindir}/reclaim_probe

%changelog
* Thu Sep 03 2026 glibc-memopt maintainers <glibc-memopt@example.invalid> 1.0.0-1
- Package the three frozen experiment tools for the HQ GBS pipeline.
