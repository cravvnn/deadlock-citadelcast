#pragma once
#include "hero_composition.hpp"
namespace hero {
// Keep the established steady rig. Only its entry is composed from the exact
// native pose along a shortest orbital arc, avoiding a chord through the hero.
class EntryRig {
    Rig tracking_;
    follow::Pose entry_{},output_{};
    double started_=0,last_=0,entry_radius_=0,entry_height_=0,entry_bearing_=0,goal_bearing_=0;
    double pitch_error_=0,yaw_error_=0,min_radius_=0,max_step_=0,max_angle_=0;
    unsigned long long entry_frames_=0;
    static constexpr double radians=3.14159265358979323846/180;
    static std::array<double,2> aim(const follow::Pose& pose,const Vec& focus){
        const double x=focus[0]-pose[0],y=focus[1]-pose[1],z=focus[2]-pose[2];
        return {-std::atan2(z,std::hypot(x,y))/radians,std::atan2(y,x)/radians};
    }
    bool fail(const char* why){tracking_.stop(why);return false;}
public:
    static constexpr double kEntryDuration=1,kMinRadius=64,kMaxEntryRadius=2048;
    bool active()const{return tracking_.active();}
    const follow::Pose& pose()const{return output_;}
    const follow::Pose& native_entry()const{return entry_;}
    const Vec& root()const{return tracking_.root();}
    const Vec& focus()const{return tracking_.focus();}
    double lag()const{return tracking_.lag();}
    double bearing()const{return tracking_.bearing();}
    unsigned long long recenters()const{return tracking_.recenters();}
    const char* reason()const{return tracking_.reason();}
    double entry_elapsed()const{return std::clamp(last_-started_,0.0,kEntryDuration);}
    bool entry_complete()const{return active()&&entry_elapsed()>=kEntryDuration;}
    unsigned long long entry_frames()const{return entry_frames_;}
    double min_radius()const{return min_radius_;}
    double max_position_step()const{return max_step_;}
    double max_angle_step()const{return max_angle_;}
    void stop(const char* why){tracking_.stop(why);}
    bool begin(double now,const Vec& root,const follow::Pose& native,HeadingPolicy policy=HeadingPolicy::NativeStart,double hero_yaw=0){
        if(active()||!std::isfinite(now)||!Finite(root)||!follow::Finite(native))return false;
        const Vec focus=Focus(root);const double x=native[0]-focus[0],y=native[1]-focus[1];
        const double radius=std::hypot(x,y);
        if(radius<kMinRadius||radius>kMaxEntryRadius)return false;
        if(!tracking_.begin(now,root,native[4],policy,hero_yaw))return false;
        entry_=output_=native;started_=last_=now;entry_frames_=0;
        entry_radius_=radius;entry_height_=native[2]-focus[2];entry_bearing_=std::atan2(y,x)/radians;
        const auto& goal=tracking_.pose();
        const double bearing=std::atan2(goal[1]-focus[1],goal[0]-focus[0])/radians;
        goal_bearing_=entry_bearing_+follow::Wrap(bearing-entry_bearing_);
        const auto looking=aim(native,focus);
        pitch_error_=follow::Wrap(native[3]-looking[0]);yaw_error_=follow::Wrap(native[4]-looking[1]);
        min_radius_=radius;max_step_=max_angle_=0;return true;
    }
    bool advance(double now,const Vec& root,bool allowed,double hero_yaw=0){
        if(!tracking_.advance(now,root,allowed,hero_yaw))return false;
        const auto& goal=tracking_.pose();const auto& focus=tracking_.focus();
        const double elapsed=now-started_;follow::Pose next=goal;
        if(elapsed<kEntryDuration){
            const double t=std::clamp(elapsed/kEntryDuration,0.0,1.0);
            // Zero first and second derivatives at both ends of the entry blend.
            const double weight=t*t*t*(10+t*(-15+6*t));
            const double x=goal[0]-focus[0],y=goal[1]-focus[1],goal_radius=std::hypot(x,y);
            if(!std::isfinite(goal_radius)||goal_radius<kMinRadius)return fail("hero entry radius unavailable");
            const double bearing=goal_bearing_+follow::Wrap(std::atan2(y,x)/radians-goal_bearing_);
            const double angle=(entry_bearing_+weight*(bearing-entry_bearing_))*radians;
            const double radius=entry_radius_+weight*(goal_radius-entry_radius_);
            next[0]=focus[0]+radius*std::cos(angle);next[1]=focus[1]+radius*std::sin(angle);
            next[2]=focus[2]+entry_height_+weight*(goal[2]-focus[2]-entry_height_);
            const auto looking=aim(next,focus);
            // Re-aim from the actual composed position each update. Decay only
            // the native framing residual, never an old moving-target angle.
            next[3]=looking[0]+(1-weight)*pitch_error_;
            next[4]=looking[1]+(1-weight)*yaw_error_;next[5]=(1-weight)*entry_[5];
            min_radius_=(std::min)(min_radius_,radius);++entry_frames_;
        }
        for(unsigned n=3;n<6;++n)next[n]=output_[n]+follow::Wrap(next[n]-output_[n]);
        if(!follow::Finite(next))return fail("hero entry pose invalid");
        if(elapsed<=kEntryDuration){
            max_step_=(std::max)(max_step_,follow::Distance(next,output_));
            for(unsigned n=3;n<6;++n)max_angle_=(std::max)(max_angle_,std::abs(follow::Wrap(next[n]-output_[n])));
        }
        output_=next;last_=now;return true;
    }
    bool copy(float* output,unsigned start,bool allowed)const{
        if(!active()||!allowed||!output||(start!=0&&start!=3))return false;
        for(unsigned n=0;n<3;++n)if(!std::isfinite(output[n]))return false;
        for(unsigned n=0;n<3;++n)output[n]=static_cast<float>(output_[start+n]);return true;
    }
};
}
