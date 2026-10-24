/* Static fixture, once per HUD instance. No camera, game commands or stat API. */
(function () {
    "use strict";
    var root = $.GetContextPanel(), probe = null, attempts = 0, shown = false, ended = false;
    var age = 0, initialDelay = 0;
    function log(message) { $.Msg("[CitadelCastUI:STATIC:v1] " + message); }
    function valid(panel) { return panel && panel.IsValid(); }
    function spectator(bar) {
        if (!valid(bar)) { return false; }
        // The stock spectate bar's CSS consumes TeamSpectator from its ancestor
        // chain. Use that exact class; do not infer observer state from a name.
        var current = bar, depth = 0;
        while (valid(current) && depth < 32) {
            if (current.BHasClass("TeamSpectator")) { return true; }
            current = current.GetParent(); depth += 1;
        }
        return false;
    }
    function finish(reason) {
        if (ended) { return; }
        ended = true;
        if (valid(probe)) { probe.SetHasClass("CCStaticVisible", false); probe.DeleteAsync(0.25); }
        log("ended reason=" + reason + "; camera writes=0; stat reads=0");
    }
    function tick() {
        if (ended) { return; }
        if (!valid(root)) { finish("hud_destroyed"); return; }
        if (!valid(probe)) { probe = root.FindChildTraverse("CitadelCastStaticProbe"); }
        if (!valid(probe)) { finish("probe_missing"); return; }
        var bar = root.FindChildTraverse("spectate_bar"), ready = spectator(bar);
        attempts += 1;
        if (shown) {
            age += 0.25;
            if (!ready) { finish("spectator_context_lost"); return; }
            if (age >= 12) { finish("complete_12s"); return; }
        } else if (ready) {
            initialDelay += 0.25;
            if (initialDelay >= 3) {
                shown = true; probe.SetHasClass("CCStaticVisible", true);
                log("shown; gate=stock_TeamSpectator; fixture=true; duration=12s");
            }
        } else { initialDelay = 0; }
        if (attempts >= 2400) { finish("waiting_limit_10min"); return; }
        $.Schedule(0.25, tick);
    }
    log("hud_script_loaded; waiting for stock spectator class; one shot; fixture=true");
    $.Schedule(0, tick);
})();
