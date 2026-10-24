/* Pure offline model. No game APIs, networking, commands, or hidden stat readers. */
(function (root) {
    "use strict";
    function finite(v) { return typeof v === "number" && isFinite(v); }
    function requireValue(ok, message) { if (!ok) { throw new Error(message); } }
    function Model(matchId, playerId, startTime) {
        requireValue(typeof matchId === "string" && matchId.length > 0, "match identity required");
        requireValue(typeof playerId === "string" && playerId.length > 0, "player identity required");
        requireValue(finite(startTime) && startTime >= 0, "valid coverage start required");
        this.matchId = matchId; this.playerId = playerId;
        this.start = startTime; this.watermark = startTime; this.confirmedThrough = startTime;
        this.events = []; this.ids = {}; this.valid = true;
    }
    Model.prototype.ingest = function (event) {
        if (!this.valid) { return false; }
        if (event.matchId !== this.matchId || event.playerId !== this.playerId) { return false; }
        requireValue(typeof event.id === "string" && event.id.length > 0 && event.id.length <= 128, "event id required");
        requireValue(finite(event.time) && event.time >= this.start, "event before observed coverage");
        requireValue(event.kind === "kill" || event.kind === "assist" || event.kind === "soulsEarned", "unsupported metric");
        requireValue(Number.isInteger(event.value) && event.value >= 0 && event.value <= 1000000, "invalid metric amount");
        requireValue(event.kind === "soulsEarned" || event.value === 1, "combat events count once");
        var key = "$" + event.id;
        if (this.ids[key]) { return false; }
        // This v0 deliberately requires an ordered, complete adapter feed. A gap,
        // seek, late correction or overflow invalidates coverage instead of lying.
        if (event.time < this.watermark || (this.confirmedThrough > this.start && event.time <= this.confirmedThrough) || this.events.length >= 4096) { this.valid = false; return false; }
        this.watermark = event.time;
        this.ids[key] = true;
        this.events.push({time:event.time, kind:event.kind, value:event.value});
        return true;
    };
    Model.prototype.invalidate = function () { this.valid = false; };
    Model.prototype.confirmThrough = function (time) {
        // Adapter attestation: ALL three metric streams were continuously covered
        // through this same spectator presentation timestamp. Not wall-clock time.
        if (!finite(time) || time < this.confirmedThrough || time < this.watermark) { this.valid = false; return false; }
        this.confirmedThrough = time; return true;
    };
    Model.prototype.snapshot = function (now, identity) {
        requireValue(finite(now) && now >= 0, "invalid presentation time");
        if (!this.valid || now < this.watermark || now > this.confirmedThrough || identity.matchId !== this.matchId || identity.playerId !== this.playerId) { return null; }
        var seconds = Math.min(120, now - this.start);
        if (seconds < 1) { return null; }
        var totals = {kill:0, assist:0, soulsEarned:0};
        var from = now - seconds;
        this.events.forEach(function(e) { if (e.time > from && e.time <= now) { totals[e.kind] += e.value; } });
        return {matchId:this.matchId, playerId:this.playerId, windowSeconds:Math.floor(seconds),
            kills:totals.kill, assists:totals.assist, soulsEarned:totals.soulsEarned,
            windowComplete:seconds === 120, asOf:now};
    };
    var api = {Model:Model, finite:finite};
    if (typeof module !== "undefined" && module.exports) { module.exports = api; }
    else { root.CitadelCastRecapModel = api; }
})(this);
