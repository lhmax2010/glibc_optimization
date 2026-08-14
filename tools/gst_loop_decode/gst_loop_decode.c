#define _POSIX_C_SOURCE 200809L

#include <gst/gst.h>

#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static volatile sig_atomic_t stop_requested;

static void
handle_stop(int signo)
{
    (void) signo;
    stop_requested = 1;
}

static void
on_demux_pad_added(GstElement *demux, GstPad *new_pad, gpointer user_data)
{
    GstElement *queue = GST_ELEMENT(user_data);
    GstPad *sink_pad;
    GstPadLinkReturn result;

    (void) demux;
    if (!g_str_has_prefix(GST_PAD_NAME(new_pad), "video_"))
        return;

    sink_pad = gst_element_get_static_pad(queue, "sink");
    if (gst_pad_is_linked(sink_pad)) {
        gst_object_unref(sink_pad);
        return;
    }
    result = gst_pad_link(new_pad, sink_pad);
    if (result != GST_PAD_LINK_OK)
        fprintf(stderr, "failed to link demux video pad: %d\n", (int) result);
    gst_object_unref(sink_pad);
}

static GstElement *
build_pipeline(const char *file)
{
    GstElement *pipeline = gst_pipeline_new("decode-pipeline");
    GstElement *source = gst_element_factory_make("filesrc", "source");
    GstElement *demux = gst_element_factory_make("qtdemux", "demux");
    GstElement *queue = gst_element_factory_make("queue", "queue");
    GstElement *parser = gst_element_factory_make("mpeg4videoparse", "parser");
    GstElement *decoder = gst_element_factory_make("avdec_mpeg4", "decoder");
    GstElement *sink = gst_element_factory_make("fakesink", "sink");

    if (pipeline == NULL || source == NULL || demux == NULL || queue == NULL
        || parser == NULL || decoder == NULL || sink == NULL) {
        fprintf(stderr, "failed to create one or more GStreamer elements\n");
        if (pipeline != NULL)
            gst_object_unref(pipeline);
        return NULL;
    }

    g_object_set(source, "location", file, NULL);
    g_object_set(sink, "sync", TRUE, NULL);
    gst_bin_add_many(GST_BIN(pipeline), source, demux, queue, parser, decoder,
                     sink, NULL);
    if (!gst_element_link(source, demux)
        || !gst_element_link_many(queue, parser, decoder, sink, NULL)) {
        fprintf(stderr, "failed to link static GStreamer elements\n");
        gst_object_unref(pipeline);
        return NULL;
    }
    g_signal_connect(demux, "pad-added", G_CALLBACK(on_demux_pad_added), queue);
    return pipeline;
}

static void
print_marker(const char *marker, unsigned int cycle)
{
    struct timespec realtime;
    struct timespec monotonic;

    clock_gettime(CLOCK_REALTIME, &realtime);
    clock_gettime(CLOCK_MONOTONIC, &monotonic);
    printf("MARKER realtime=%lld.%09ld monotonic=%lld.%09ld cycle=%u state=%s\n",
           (long long) realtime.tv_sec, realtime.tv_nsec,
           (long long) monotonic.tv_sec, monotonic.tv_nsec, cycle, marker);
    fflush(stdout);
}

static int
sleep_seconds(unsigned int seconds)
{
    struct timespec remaining = { .tv_sec = seconds, .tv_nsec = 0 };

    while (!stop_requested && nanosleep(&remaining, &remaining) == -1) {
        if (errno != EINTR) {
            perror("nanosleep");
            return -1;
        }
    }
    return stop_requested ? 1 : 0;
}

static unsigned int
parse_uint(const char *text, const char *name, int allow_zero)
{
    char *end = NULL;
    unsigned long value;

    errno = 0;
    value = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value > UINT32_MAX
        || (!allow_zero && value == 0)) {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(2);
    }
    return (unsigned int) value;
}

static void
report_bus_errors(GstElement *pipeline)
{
    GstBus *bus = gst_element_get_bus(pipeline);
    GstMessage *message;

    while ((message = gst_bus_pop_filtered(
                bus, GST_MESSAGE_ERROR | GST_MESSAGE_WARNING)) != NULL) {
        GError *error = NULL;
        char *debug = NULL;

        if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR)
            gst_message_parse_error(message, &error, &debug);
        else
            gst_message_parse_warning(message, &error, &debug);
        fprintf(stderr, "bus %s from %s: %s; debug=%s\n",
                GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR
                    ? "error" : "warning",
                GST_OBJECT_NAME(message->src),
                error != NULL ? error->message : "unknown error",
                debug != NULL ? debug : "none");
        g_clear_error(&error);
        g_free(debug);
        gst_message_unref(message);
    }
    gst_object_unref(bus);
}

static int
set_state_and_wait(GstElement *pipeline, GstState state, const char *name)
{
    GstStateChangeReturn result;

    result = gst_element_set_state(pipeline, state);
    if (result == GST_STATE_CHANGE_FAILURE) {
        fprintf(stderr, "gst_element_set_state(%s) failed\n", name);
        report_bus_errors(pipeline);
        return -1;
    }

    result = gst_element_get_state(pipeline, NULL, NULL, 30 * GST_SECOND);
    if (result == GST_STATE_CHANGE_FAILURE || result == GST_STATE_CHANGE_ASYNC) {
        fprintf(stderr, "gst_element_get_state(%s) did not complete: %d\n",
                name, (int) result);
        report_bus_errors(pipeline);
        return -1;
    }
    return 0;
}

int
main(int argc, char **argv)
{
    const unsigned int initial_wait_seconds = 5;
    GstElement *pipeline;
    unsigned int cycles;
    unsigned int play_seconds;
    unsigned int null_seconds;
    unsigned int cycle;
    int status = 0;

    if (argc != 5) {
        fprintf(stderr,
                "usage: %s <file> <cycles> <play_seconds> <null_seconds>\n",
                argv[0]);
        return 2;
    }

    cycles = parse_uint(argv[2], "cycles", 0);
    play_seconds = parse_uint(argv[3], "play_seconds", 0);
    null_seconds = parse_uint(argv[4], "null_seconds", 1);

    signal(SIGINT, handle_stop);
    signal(SIGTERM, handle_stop);
    gst_init(&argc, &argv);

    pipeline = build_pipeline(argv[1]);
    if (pipeline == NULL) {
        return 3;
    }

    print_marker("PROCESS_READY", 0);
    print_marker("INITIAL_WAIT_START", 0);
    if (sleep_seconds(initial_wait_seconds) != 0)
        goto out;

    for (cycle = 1; cycle <= cycles && !stop_requested; ++cycle) {
        print_marker("PLAYING_REQUEST", cycle);
        if (set_state_and_wait(pipeline, GST_STATE_PLAYING, "PLAYING") != 0) {
            status = 4;
            goto out;
        }
        print_marker("PLAYING_START", cycle);
        if (sleep_seconds(play_seconds) != 0)
            break;

        print_marker("NULL_REQUEST", cycle);
        if (set_state_and_wait(pipeline, GST_STATE_NULL, "NULL") != 0) {
            status = 5;
            goto out;
        }
        print_marker("NULL_DONE", cycle);
        print_marker("NULL_WAIT_START", cycle);
        if (sleep_seconds(null_seconds) != 0)
            break;
        print_marker("CYCLE_DONE", cycle);
    }

    if (!stop_requested) {
        print_marker("FINAL_WAIT_START", cycles);
        sleep_seconds(null_seconds > 0 ? null_seconds : 10);
    }

out:
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_element_get_state(pipeline, NULL, NULL, 30 * GST_SECOND);
    gst_object_unref(pipeline);
    print_marker(stop_requested ? "STOPPED" : "PROCESS_EXIT", cycles);
    return status;
}
