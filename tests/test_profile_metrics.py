from retrotui.core.profile_metrics import parse_profile_metrics


def test_parse_profile_metrics_reads_startup_and_profile_final():
    lines = [
        'ts=... level=DEBUG logger=retrotui.__main__ msg="startup boot_ms=83.21 use_unicode=True windows=1 icons=10"',
        'ts=... level=DEBUG logger=retrotui.core.event_loop msg="profile elapsed_s=5.000 loops=300 redraws=42 redraw_ratio=0.140 events=17 draw_ms=10.00 dispatch_ms=3.20 input_wait_ms=4986.80"',
        'ts=... level=DEBUG logger=retrotui.core.event_loop msg="profile_final elapsed_s=8.000 loops=480 redraws=61 clock_refreshes=8 redraw_ratio=0.127 events=23 invalidations_notification=2 invalidations_tick=19 invalidations_input=23 background_ms=4.50 tick_ms=12.25 draw_ms=18.50 dispatch_ms=5.10 input_wait_ms=7976.40 max_tick_ms=1.20 max_draw_ms=3.40 max_dispatch_ms=0.80"',
    ]

    out = parse_profile_metrics(lines)

    assert out.boot_ms == 83.21
    assert out.redraw_ratio == 0.127
    assert out.loops == 480
    assert out.redraws == 61
    assert out.events == 23
    assert out.draw_ms == 18.5
    assert out.dispatch_ms == 5.1
    assert out.input_wait_ms == 7976.4
    assert out.background_ms == 4.5
    assert out.tick_ms == 12.25
    assert out.max_tick_ms == 1.2
    assert out.max_draw_ms == 3.4
    assert out.max_dispatch_ms == 0.8
    assert out.clock_refreshes == 8
    assert out.notification_invalidations == 2
    assert out.tick_invalidations == 19
    assert out.input_invalidations == 23


def test_parse_profile_metrics_handles_missing_profile_final():
    lines = [
        'ts=... msg="startup boot_ms=55.00 use_unicode=True windows=1 icons=8"',
        'ts=... msg="profile elapsed_s=2.0 loops=100 redraws=20 redraw_ratio=0.2"',
    ]

    out = parse_profile_metrics(lines)

    assert out.boot_ms == 55.0
    assert out.redraw_ratio is None
    assert out.loops is None
