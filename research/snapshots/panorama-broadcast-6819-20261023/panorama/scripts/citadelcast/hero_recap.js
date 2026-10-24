/* Proposed bridge contract only; NOT connected to a native camera/data provider. */
(function () {
    "use strict";
    var panel = $.GetContextPanel(), generation = 0;
    var active = null, heartbeat = 0;
    function hide() {
        generation += 1; active = null;
        panel.SetHasClass("Visible", false);
        panel.SetHasClass("HeadAnchor", false);
        $("#RecapCard").style.position = "0px 0px 0px";
    }
    function validNumber(v) { return typeof v === "number" && isFinite(v) && v >= 0; }
    function validId(v) { return typeof v === "string" && v.length > 0 && v.length <= 128; }
    function count(v) { return validNumber(v) && Math.floor(v) === v; }
    function show(context, recap) {
        hide();
        if (!context || !recap || context.offair !== true || context.observer !== true ||
            context.cameraSettled !== true || context.mode !== "turn-with-hero" ||
            !validId(context.takeId) || !validId(context.matchId) || !validId(context.playerId) ||
            context.matchId !== recap.matchId || context.playerId !== recap.playerId ||
            !count(recap.windowSeconds) || recap.windowSeconds < 1 || recap.windowSeconds > 120 ||
            !count(recap.kills) || !count(recap.assists) || !count(recap.soulsEarned) ||
            !validNumber(recap.asOf) || !validNumber(context.now) || context.now < recap.asOf || context.now - recap.asOf > 1 ||
            typeof context.playerName !== "string") { return false; }
        active = {takeId:context.takeId, matchId:context.matchId, playerId:context.playerId};
        panel.SetHasClass("Sapphire", context.team === "sapphire");
        $("#RecapPlayer").text = context.playerName.slice(0, 64);
        $("#RecapWindow").text = "LAST " + recap.windowSeconds + "s";
        $("#RecapKills").text = String(recap.kills);
        $("#RecapAssists").text = String(recap.assists);
        $("#RecapSouls").text = "+" + recap.soulsEarned;
        panel.SetHasClass("Visible", true);
        var token = generation;
        function watch(lastHeartbeat) {
            $.Schedule(0.5, function () {
                if (token !== generation) { return; }
                if (lastHeartbeat === heartbeat) { hide(); return; }
                watch(heartbeat);
            });
        }
        watch(heartbeat);
        $.Schedule(7, function () { if (token === generation) { hide(); } });
        return true;
    }
    function sync(context) {
        if (!active || !context || context.takeId !== active.takeId || context.matchId !== active.matchId ||
            context.playerId !== active.playerId || context.cameraSettled !== true ||
            context.observer !== true || context.offair !== true || context.mode !== "turn-with-hero") { hide(); return false; }
        heartbeat += 1;
        return true;
    }
    function anchor(context, projection) {
        if (!sync(context)) { return false; }
        // Projection is future adapter-supplied PANEL coordinates, not a guessed
        // Panorama world-to-screen API. Missing/unsafe projection hides the card.
        if (!projection || projection.visible !== true || projection.occluded !== false ||
            !validNumber(projection.x) || !validNumber(projection.y) ||
            !validNumber(projection.viewportWidth) || !validNumber(projection.viewportHeight) ||
            projection.x < 24 || projection.y < 100 ||
            projection.x + 460 > projection.viewportWidth - 24 ||
            projection.y + 220 > projection.viewportHeight - 220) { hide(); return false; }
        panel.SetHasClass("HeadAnchor", true);
        $("#RecapCard").style.position = projection.x + "px " + projection.y + "px 0px";
        return true;
    }
    panel.CitadelCastRecap = {show:show, hide:hide, sync:sync, anchor:anchor};
    hide();
})();
