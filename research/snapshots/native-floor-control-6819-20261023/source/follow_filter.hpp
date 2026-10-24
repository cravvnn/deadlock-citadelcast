#pragma once
#include <algorithm>
#include <array>
#include <cmath>

namespace follow {
using Pose=std::array<double,6>; // position xyz, native pitch/yaw/roll in degrees
inline bool Finite(const Pose& pose) { return std::all_of(pose.begin(),pose.end(),[](double v){return std::isfinite(v);}); }
inline double Wrap(double angle) { return std::remainder(angle,360.0); }
inline double Distance(const Pose& a,const Pose& b) { return std::hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]); }

// A view-pose filter, NOT an entity tracker or replacement collision solver.
// All inputs are native camera output; no engine memory or process API here.
class Filter {
    Pose raw_{},output_{};
    double last_=0;
    bool active_=false;
    const char* reason_="idle";
public:
    static constexpr double kResponse=.25,kMaxGap=.25,kMaxStep=512,kMaxLag=256;
    bool active()const{return active_;}
    const Pose& pose()const{return output_;}
    const Pose& native()const{return raw_;}
    const char* reason()const{return reason_;}
    void stop(const char* reason){active_=false;reason_=reason;}
    bool begin(double now,const Pose& native){
        if(active_ || !std::isfinite(now) || !Finite(native))return false;
        raw_=output_=native;last_=now;active_=true;reason_="filtering";return true;
    }
    bool advance(double now,const Pose& native,bool permitted){
        if(!active_)return false;
        if(!permitted){stop("follow gate changed");return false;}
        if(!std::isfinite(now) || !Finite(native) || now<last_){stop("invalid follow sample/clock");return false;}
        const double dt=now-last_;
        if(dt>kMaxGap){stop("follow frame gap");return false;}
        if(Distance(raw_,native)>kMaxStep){stop("native camera discontinuity");return false;}
        for(unsigned n=3;n<6;++n)if(std::abs(Wrap(native[n]-raw_[n]))>90){stop("native angle discontinuity");return false;}
        Pose next=output_;const double alpha=-std::expm1(-dt/kResponse);
        for(unsigned n=0;n<3;++n)next[n]+=alpha*(native[n]-next[n]);
        for(unsigned n=3;n<6;++n)next[n]=Wrap(next[n]+alpha*Wrap(native[n]-next[n]));
        if(!Finite(next) || Distance(next,native)>kMaxLag){stop("follow lag bound");return false;}
        output_=next;raw_=native;last_=now;return true;
    }
    bool copy(float* native_output,unsigned start,bool permitted)const{
        if(!active_ || !permitted || !native_output || (start!=0 && start!=3))return false;
        for(unsigned n=0;n<3;++n)if(!std::isfinite(native_output[n]))return false;
        for(unsigned n=0;n<3;++n)native_output[n]=static_cast<float>(output_[start+n]);
        return true;
    }
};
}
