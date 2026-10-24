#pragma once
#include <cmath>
#include "walker_shot.hpp"

namespace walker {
enum class Phase { Idle, Countdown, Playing, Endpoint };
enum class Action { None, Begin, Apply, Complete, Cancel };
struct Gates {
    bool identity=true, foreground=true, viewer=true, input_idle=true, camera=true;
    bool valid() const { return identity && foreground && viewer && input_idle && camera; }
};
struct Tick { Action action=Action::None; double time=0; const char* reason="idle"; };

// The caller supplies one monotonic clock for every channel. No serial sleeps,
// frame-count timing, interpolation approximation or live cvar writes here.
class Playback {
    Phase phase_=Phase::Idle;
    double armed_=0, started_=0, last_=0,duration_=kDuration;
public:
    Phase phase() const { return phase_; }
    bool active() const { return phase_!=Phase::Idle; }
    double duration() const { return duration_; }
    bool arm(double now, const Gates& gates,double duration=kDuration) {
        if(active() || !gates.valid() || !std::isfinite(now) || !std::isfinite(duration) || duration<=0 || duration>3600) return false;
        duration_=duration;phase_=Phase::Countdown; armed_=last_=now; return true;
    }
    Tick cancel(const char* why) { phase_=Phase::Idle; return {Action::Cancel,0,why}; }
    bool begin_ready(double now) {
        if(phase_!=Phase::Playing || !std::isfinite(now) || now<last_) return false;
        started_=last_=now; return true;
    }
    double elapsed(double now) const { return std::clamp(now-started_,0.0,duration_); }
    Tick step(double now, const Gates& gates) {
        if(!active()) return {};
        if(!gates.valid()) return cancel("ownership/focus/viewer/input gate changed");
        if(!std::isfinite(now) || now<last_) return cancel("invalid monotonic clock");
        const double gap=now-last_; last_=now;
        if(phase_==Phase::Countdown) {
            if(now-armed_<3.0) return {Action::None,0,"countdown"};
            if(now-armed_>4.0) return cancel("countdown update missed");
            phase_=Phase::Playing; started_=now;
            return {Action::Begin,0,"begin"};
        }
        if(gap>0.5) return cancel("frame gap exceeds playback bound");
        if(phase_==Phase::Endpoint) { phase_=Phase::Idle; return {Action::Complete,duration_,"complete"}; }
        const double elapsed=now-started_;
        if(elapsed>=duration_) {
            phase_=Phase::Endpoint; return {Action::Apply,duration_,"endpoint"};
        }
        return {Action::Apply,elapsed,"playing"};
    }
};

// A restoration must not replace an operator's later framing change.
inline bool MayRestoreAspect(float current,float last_owned,bool wrote) {
    return wrote && std::isfinite(current) && current==last_owned;
}
} // namespace walker
