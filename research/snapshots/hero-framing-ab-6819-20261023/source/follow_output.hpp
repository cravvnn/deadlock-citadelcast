#pragma once
#include "follow_filter.hpp"

namespace follow {
// Full ownership/viewer/focus/input checks belong to camera frames, not each
// pose getter. A getter can only consume a checked sample from this frame and
// never during native camera math. No cached permit survives a frame boundary,
// a failed check, a stop, or more than the filter's existing gap bound.
class FramePermit {
    bool ready_=false;
    double checked_at_=0;
    unsigned native_depth_=0;
public:
    void invalidate(){ready_=false;}
    template<class Check> bool refresh(double now,Check check){
        invalidate();
        if(!std::isfinite(now) || !check())return false;
        checked_at_=now;ready_=true;return true;
    }
    bool allows(double now)const{
        return ready_ && !native_depth_ && std::isfinite(now) &&
            now>=checked_at_ && now-checked_at_<=Filter::kMaxGap;
    }
    template<class Output> bool copy(const Output& filter,float* output,unsigned start,bool selected,double now)const{
        return filter.copy(output,start,selected && allows(now));
    }
    class NativeUpdate {
        FramePermit& permit_;
    public:
        explicit NativeUpdate(FramePermit& permit):permit_(permit){++permit_.native_depth_;}
        ~NativeUpdate(){--permit_.native_depth_;}
        NativeUpdate(const NativeUpdate&)=delete;
        NativeUpdate& operator=(const NativeUpdate&)=delete;
    };
};
} // namespace follow
