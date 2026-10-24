#pragma once
#include "follow_filter.hpp"

namespace hero {
using Vec=std::array<double,3>;
enum class HeadingPolicy { NativeStart, HeroStart, HeroFollow };
inline const char* Profile(HeadingPolicy p){
    return p==HeadingPolicy::HeroFollow?"turn-with-hero":p==HeadingPolicy::HeroStart?"hold-bearing":"legacy-native-bearing";
}
inline bool Finite(const Vec& p){return std::all_of(p.begin(),p.end(),[](double v){return std::isfinite(v) && std::abs(v)<1e7;});}
inline double Length(const Vec& p){return std::hypot(p[0],p[1],p[2]);}
inline Vec Focus(const Vec& root){return {root[0],root[1],root[2]+48};}
// Authored composition values, not entity structure offsets. Legacy retains
// its native-heading start; A/B both use hero world facing+45deg. HeroFollow
// turns the bearing with a bounded shortest-angle response; HeroStart holds it.
// Smooth translation, then aim at the CURRENT target point.
class Rig {
    follow::Pose pose_{};
    Vec root_{},focus_{},offset_{};
    double last_=0,lag_=0,bearing_=0;
    HeadingPolicy policy_=HeadingPolicy::NativeStart;
    void offset(){
        const double angle=bearing_*3.14159265358979323846/180;
        offset_={kRadius*std::cos(angle),kRadius*std::sin(angle),kElevation};
    }
    bool active_=false;
    unsigned long long recenters_=0;
    const char* reason_="idle";
    bool aim(){
        const double x=focus_[0]-pose_[0],y=focus_[1]-pose_[1],z=focus_[2]-pose_[2];
        if(std::hypot(x,y,z)<64)return false;
        constexpr double degrees=180/3.14159265358979323846;
        pose_[3]=-std::atan2(z,std::hypot(x,y))*degrees;
        pose_[4]=std::atan2(y,x)*degrees;pose_[5]=0;
        return follow::Finite(pose_);
    }
public:
    static constexpr double kRadius=260,kElevation=36,kResponse=.25,kMaxLag=128;
    static constexpr double kTurnResponse=.35,kMaxTurnRate=90;
    double bearing()const{return bearing_;}
    bool active()const{return active_;}
    const follow::Pose& pose()const{return pose_;}
    const Vec& focus()const{return focus_;}
    const Vec& root()const{return root_;}
    double lag()const{return lag_;}
    unsigned long long recenters()const{return recenters_;}
    const char* reason()const{return reason_;}
    void stop(const char* reason){active_=false;reason_=reason;}
    bool begin(double now,const Vec& root,double native_heading,HeadingPolicy policy=HeadingPolicy::NativeStart,double hero_yaw=0){
        if(active_ || !std::isfinite(now) || !Finite(root) || !std::isfinite(native_heading) ||
            (policy!=HeadingPolicy::NativeStart && !std::isfinite(hero_yaw)))return false;
        policy_=policy;bearing_=(policy==HeadingPolicy::NativeStart?native_heading:hero_yaw)+45;offset();
        root_=root;focus_=Focus(root);last_=now;lag_=0;recenters_=0;
        for(unsigned n=0;n<3;++n)pose_[n]=focus_[n]+offset_[n];
        active_=aim();reason_=active_?"tracking":"invalid hero framing";return active_;
    }
    bool advance(double now,const Vec& root,bool allowed,double hero_yaw=0){
        if(!active_)return false;
        if(!allowed || !std::isfinite(now) || now<last_ || !Finite(root) ||
            (policy_!=HeadingPolicy::NativeStart && !std::isfinite(hero_yaw))){
            stop("hero target/gate/clock changed");return false;
        }
        const double dt=now-last_;Vec step{};
        for(unsigned n=0;n<3;++n)step[n]=root[n]-root_[n];
        if(dt>follow::Filter::kMaxGap || Length(step)>follow::Filter::kMaxStep){
            stop("hero frame gap or target discontinuity");return false;
        }
        if(policy_==HeadingPolicy::HeroFollow){
            const double error=follow::Wrap(hero_yaw+45-bearing_);
            bearing_+=std::clamp(-std::expm1(-dt/kTurnResponse)*error,-kMaxTurnRate*dt,kMaxTurnRate*dt);
            offset();
        }
        root_=root;focus_=Focus(root);
        const double alpha=-std::expm1(-dt/kResponse);Vec error{};
        for(unsigned n=0;n<3;++n){
            const double desired=focus_[n]+offset_[n];
            pose_[n]+=alpha*(desired-pose_[n]);error[n]=desired-pose_[n];
        }
        lag_=Length(error);
        // Keep bounded separation during ordinary dashes. This tighter128unit
        // positional envelope is within the existing256unit filter bound;
        // >512unit target jumps still CANCEL, with no guessed target recovery.
        if(lag_>kMaxLag){
            for(unsigned n=0;n<3;++n)pose_[n]=focus_[n]+offset_[n]-error[n]*(kMaxLag/lag_);
            lag_=kMaxLag;++recenters_;
        }
        if(!aim()){stop("invalid hero framing");return false;}
        last_=now;return true;
    }
    bool copy(float* output,unsigned start,bool allowed)const{
        if(!active_ || !allowed || !output || (start!=0 && start!=3))return false;
        for(unsigned n=0;n<3;++n)if(!std::isfinite(output[n]))return false;
        for(unsigned n=0;n<3;++n)output[n]=static_cast<float>(pose_[start+n]);
        return true;
    }
};
} // namespace hero
